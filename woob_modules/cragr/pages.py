# Copyright(C) 2023 Powens
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

import re

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Coalesce, Env, Format
from woob.browser.pages import JsonPage
from woob.capabilities.bank import Account, Transaction
from woob.capabilities.base import NotAvailable
from woob.tools.date import parse_french_date


FAMILY_TYPES = {
    "COMPTES": Account.TYPE_CHECKING,
    "EPARGNE": Account.TYPE_SAVINGS,
    "CREDITS": Account.TYPE_LOAN,
    "PLACEMENTS": Account.TYPE_MARKET,
}

# Affinage par libellé commercial quand il lève l'ambiguïté de la grande famille.
LABEL_TYPES = {
    "PEA": Account.TYPE_PEA,
    "Livret A": Account.TYPE_SAVINGS,
    "LDD": Account.TYPE_SAVINGS,
    "PEL": Account.TYPE_SAVINGS,
    "CEL": Account.TYPE_SAVINGS,
    "Parts Sociales": Account.TYPE_MARKET,
}

# Le BFF décrit le type d'opération en clair dans libelleTypeOperation ("PAIEMENT PAR
# CARTE", "PRELEVEMENT", "VIREMENT EMIS"...). On le mappe vers les types woob pour que
# l'export (OFX TRNTYPE) et l'affichage gardent le bon type, sans recopier ce libellé
# dans le label de l'opération (sinon il pollue le champ bénéficiaire à l'import).
# L'ordre compte : les frais sont testés avant CARTE (une cotisation carte reste BANK)
# et REMISE avant CHEQUE (une remise de chèque est un dépôt, pas un chèque émis).
TRANSACTION_TYPES = [
    ("COTISATION", Transaction.TYPE_BANK),
    ("FRAIS", Transaction.TYPE_BANK),
    ("INTERETS", Transaction.TYPE_BANK),
    ("CARTE", Transaction.TYPE_CARD),
    ("PRELEVEMENT", Transaction.TYPE_ORDER),
    ("VIREMENT", Transaction.TYPE_TRANSFER),
    ("RETRAIT", Transaction.TYPE_WITHDRAWAL),
    ("REMISE", Transaction.TYPE_DEPOSIT),
    ("CHEQUE", Transaction.TYPE_CHECK),
]


def parse_cragr_date(text):
    # Les dates arrivent en toutes lettres ("Mercredi 17 juin 2026") : on retire
    # le jour de la semaine avant de les parser.
    if not text:
        return NotAvailable
    parts = text.split(" ", 1)
    if len(parts) > 1:
        text = parts[1]
    return parse_french_date(text).date()


class CragrJsonPage(JsonPage):
    def build_doc(self, text):
        # Certaines familles de comptes (CREDITS, PLACEMENTS…) renvoient un corps
        # vide avec un code 200 : on le traite comme un document vide.
        if not text or not text.strip():
            return {}
        return super().build_doc(text)


class AppConfigPage(CragrJsonPage):
    def get_client_id(self):
        # espace-client moved clientId under "mireOptions" while detail-dav keeps
        # it at the root: accept both locations.
        return Coalesce(
            Dict("mireOptions/clientId", default=NotAvailable),
            Dict("clientId", default=NotAvailable),
        )(self.doc)

    def get_structure_id(self, region):
        for bank in Dict("regionalBanks", default=[])(self.doc):
            if bank.get("identifier") == region:
                return bank.get("structureId")
        return None


class SecurityUserPage(CragrJsonPage):
    def get_state(self):
        return Dict("state", default=None)(self.doc)

    def get_csid(self):
        return Dict("csid", default=None)(self.doc)


class KeypadPage(CragrJsonPage):
    def build_password(self, password):
        # Le code n'est pas transmis en clair : on envoie la position de chaque
        # chiffre dans le clavier renvoyé par le serveur.
        layout = Dict("keys_layout")(self.doc)
        return f"[{','.join(str(layout.index(digit)) for digit in password)}]"


class LoginValidationPage(CragrJsonPage):
    def has_captcha(self):
        return Dict("captcha", default=False)(self.doc)

    def is_authenticated(self):
        return Dict("step", default=None)(self.doc) == "AUTHENTICATED"

    def get_redirect_url(self):
        return Dict("redirect_url", default=None)(self.doc)


class SsoPage(CragrJsonPage):
    def get_context_id(self):
        return Dict("context_id")(self.doc)


class AccountsPage(CragrJsonPage):
    @method
    class iter_accounts(DictElement):
        # Le BFF renvoie parfois un même compte deux fois dans une grande famille
        # (numero_compte dupliqué) : on ignore le doublon au lieu de lever DataError.
        ignore_duplicate = True

        def find_elements(self):
            return self.page.doc.get(Env("family")(self)) or []

        class item(ItemElement):
            klass = Account

            obj_id = Coalesce(
                CleanText(Dict("numero_compte", default=None), default=""),
                CleanText(Dict("id_element_contrat", default=None), default=""),
                default="",
            )
            obj_number = CleanText(Dict("numero_compte", default=None), default=NotAvailable)
            obj_label = Coalesce(
                CleanText(Dict("libelle_produit_commercial", default=None), default=""),
                CleanText(Dict("libelle", default=None), default=""),
                default=NotAvailable,
            )
            obj_currency = CleanText(Dict("code_devise", default=None), default="EUR")
            obj__id_element_contrat = Dict("id_element_contrat", default=None)

            def obj_balance(self):
                # Les crédits ne portent pas de solde mais un capital restant dû, renvoyé
                # en valeur négative (une dette). Restreint à la famille CREDITS pour ne pas
                # inverser par erreur le solde d'un compte d'une autre famille.
                if Env("family")(self) == "CREDITS":
                    capital = CleanDecimal.US(Dict("montant_capital_restant_du", default=None), default=None)(self)
                    if capital is not None:
                        return -abs(capital)
                return CleanDecimal.US(
                    Coalesce(Dict("solde_valeur", default=None), Dict("solde", default=None), default=NotAvailable),
                    default=NotAvailable,
                )(self)

            def obj_type(self):
                label = CleanText(Dict("libelle_produit_commercial", default=""))(self)
                for key, account_type in LABEL_TYPES.items():
                    if key.lower() in label.lower():
                        return account_type
                return FAMILY_TYPES.get(Env("family")(self), Account.TYPE_UNKNOWN)


class TransactionItem(ItemElement):
    klass = Transaction

    obj_id = CleanText(Dict("id"))
    obj_amount = CleanDecimal.US(Dict("montant"))
    obj_raw = CleanText(
        Format(
            "%s %s %s",
            CleanText(Dict("libelleTypeOperation", default=None), default=""),
            CleanText(Dict("libelleOperation", default=None), default=""),
            CleanText(Dict("libelleComplementaire", default=None), default=""),
        )
    )
    # Le complément (réf détaillée) alimente le champ MEMO de l'export OFX via category :
    # l'exporteur (woob/applications/bank/bank.py) lit obj.category pour le MEMO. On passe
    # par category (champ déclaré, lu par toutes les versions de woob) plutôt que _memo,
    # qui n'est honoré que par les woob récents. Le type est déjà porté par TRNTYPE
    # (obj_type). Coalesce ramène un complément vide à NotAvailable (pas de MEMO vide).
    obj_category = Coalesce(
        CleanText(Dict("libelleComplementaire", default=None), default=""),
        default=NotAvailable,
    )

    def obj_label(self):
        # Le label ne porte que le libellé de l'opération (bénéficiaire/commerçant) : c'est
        # lui qui alimente le champ NAME des exports OFX, indexé par les logiciels de compta.
        # Le type d'opération reste dans obj_raw et obj_type, pas dans le label.
        label = Coalesce(
            CleanText(Dict("libelleOperation", default=None), default=""),
            CleanText(Dict("libelleTypeOperation", default=None), default=""),
            default="",
        )(self)
        # La nouvelle API renvoie la date de l'opération (jj/mm, parfois jj/mm/aaaa) collée
        # en fin de libellé, ce que l'ancien site ne faisait pas. On la retire pour ne pas
        # créer de faux doublons côté apps qui dédupliquent sur le libellé ; la date reste
        # portée par obj_date.
        label = re.sub(r"\s+\d{2}/\d{2}(?:/\d{2,4})?$", "", label)
        return label or NotAvailable

    def obj_type(self):
        label = CleanText(Dict("libelleTypeOperation", default=""))(self).upper()
        for keyword, tr_type in TRANSACTION_TYPES:
            if keyword in label:
                return tr_type
        return Transaction.TYPE_UNKNOWN

    def obj_date(self):
        return parse_cragr_date(Dict("dateOperationAffichee", default=None)(self))

    def obj_rdate(self):
        return parse_cragr_date(Dict("dateValeurAffichee", default=None)(self))


class HistoryPage(CragrJsonPage):
    def has_next(self):
        return bool(Dict("hasNext", default=False)(self.doc))

    @method
    class iter_history(DictElement):
        def find_elements(self):
            for bloc in self.page.doc.get("operationBlocs") or []:
                yield from bloc.get("operationDetails", [])

        item = TransactionItem


class ComingPage(CragrJsonPage):
    @method
    class iter_coming(DictElement):
        def find_elements(self):
            for section in ("carteDebitImmediat", "autreOperation"):
                section_data = self.page.doc.get(section) or {}
                for bloc in section_data.get("operationBlocs") or []:
                    yield from bloc.get("operationDetails", [])

        item = TransactionItem
