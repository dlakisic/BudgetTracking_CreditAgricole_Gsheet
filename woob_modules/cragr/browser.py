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

import base64
import json
import re
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from woob.browser import URL, LoginBrowser, need_login
from woob.capabilities.bank import Account
from woob.exceptions import ActionNeeded, BrowserIncorrectPassword, BrowserUnavailable

from .pages import (
    AccountsPage,
    AppConfigPage,
    ComingPage,
    HistoryPage,
    KeypadPage,
    LoginValidationPage,
    SecurityUserPage,
    SsoPage,
)


CHROME_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"


class CreditAgricoleBrowser(LoginBrowser):
    TIMEOUT = 30.0

    BASEURL = "https://espace-client.credit-agricole.fr"
    CACONNECT = "https://client.ca-connect.credit-agricole.fr"
    DETAILDAV = "https://detail-dav.credit-agricole.fr"

    # espace-client (synthèse)
    espace_config = URL(r"/assets/configuration/app-config.json", AppConfigPage)
    security_user = URL(r"/bff/api/security/user", SecurityUserPage)
    security_login = URL(r"/bff/api/security/login")
    sso = URL(r"/bff/api/context/sso/v1", SsoPage)
    accounts = URL(r"/bff/api/synthesis/contract/data", AccountsPage)

    # client.ca-connect (authentification OAuth)
    caconnect_config = URL(r"/fe/assets/configuration/app-config.json", AppConfigPage, base="CACONNECT")
    authorize = URL(r"/authorize", base="CACONNECT")
    context = URL(r"/bff/api/context", base="CACONNECT")
    auth_username = URL(r"/bff/api/authentication/username", base="CACONNECT")
    keypad = URL(r"/bff/api/authentication/keypad", KeypadPage, base="CACONNECT")
    login_validation = URL(r"/bff/api/authentication/login", LoginValidationPage, base="CACONNECT")

    # detail-dav (détail d'un compte + opérations), chemins préfixés par la région
    dav_config = URL(r"/(?P<region>[\w-]+)/fe/assets/configuration/app-config.json", AppConfigPage, base="DETAILDAV")
    dav_fe = URL(r"/(?P<region>[\w-]+)/fe/", base="DETAILDAV")
    dav_logout = URL(r"/(?P<region>[\w-]+)/bff/security/standalonelogout", base="DETAILDAV")
    dav_user = URL(r"/(?P<region>[\w-]+)/bff/security/user", SecurityUserPage, base="DETAILDAV")
    dav_login = URL(r"/(?P<region>[\w-]+)/bff/security/login", base="DETAILDAV")
    dav_context = URL(r"/(?P<region>[\w-]+)/bff/context", base="DETAILDAV")
    dav_operations = URL(r"/(?P<region>[\w-]+)/bff/operations/imputees", HistoryPage, base="DETAILDAV")
    dav_coming = URL(r"/(?P<region>[\w-]+)/bff/operations/a-venir/detail", ComingPage, base="DETAILDAV")

    # /operations/imputees est cumulatif et sans pagination par paramètre : chaque
    # appel renvoie tout le déjà-chargé plus ~90 opérations. On le rappelle jusqu'à
    # hasNext=False (garde-fou pour borner les très gros comptes).
    MAX_HISTORY_CALLS = 50

    def __init__(self, website, username, password, *args, **kwargs):
        super().__init__(username, password, *args, **kwargs)
        self.website = website
        self.region = re.sub(r"^www\.", "", website).replace(".fr", "")
        self.client_id = None
        self.structure_id = None
        self.oauth_params = None
        self._logged = False
        self.session.headers.update(
            {
                "User-Agent": CHROME_UA,
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

    @property
    def logged(self):
        return self._logged

    def _xsrf(self, host):
        # Cookie XSRF-TOKEN posé avec un domaine à point initial et renouvelé à
        # chaque réponse : on relit la valeur courante du domaine le plus précis.
        best = ("", "")
        for cookie in self.session.cookies:
            if cookie.name != "XSRF-TOKEN":
                continue
            domain = cookie.domain.lstrip(".")
            if (host == domain or host.endswith("." + domain)) and len(domain) > len(best[0]):
                best = (domain, cookie.value or "")
        return best[1]

    def build_request(self, url, *args, **kwargs):
        # Le token anti-CSRF doit accompagner chaque requête (obligatoire sur les
        # POST). On l'ajoute automatiquement selon l'hôte visé.
        if isinstance(url, str):
            target = url
        else:
            target = getattr(url, "url", "") or ""
        host = urlparse(target).netloc
        headers = kwargs.setdefault("headers", {})
        if host:
            token = self._xsrf(host)
            if token:
                headers.setdefault("x-xsrf-token", token)
        if "ca-connect" in host:
            headers.setdefault("x-auth-login", self.username or "")
            headers.setdefault("corr_id", str(uuid4()))
        return super().build_request(url, *args, **kwargs)

    def do_login(self):
        if not self.username or not self.password:
            raise BrowserIncorrectPassword()

        self.client_id = self.espace_config.go().get_client_id()
        self.structure_id = self.caconnect_config.go().get_structure_id(self.region)
        if not self.structure_id:
            raise BrowserUnavailable("Caisse régionale inconnue : %s" % self.region)

        redirect_uri = f"{self.BASEURL}/{self.region}/particulier"

        # Le BFF génère le state/csid de la session OAuth : on doit les réutiliser
        # (un state fabriqué mène à « Identifiants de session invalides »).
        self.location(redirect_uri)
        self.security_user.go()
        state = self.page.get_state()
        csid = self.page.get_csid()
        if not state:
            raise BrowserUnavailable("Initialisation de session impossible")

        nav_context_data = {
            "marche_derive": "particulier",
            "code_charte": "V",
            "portail_origine": "PortailClient",
            "theme": "light",
            "csid": csid,
        }
        nav_context = base64.b64encode(json.dumps(nav_context_data, separators=(",", ":")).encode()).decode()

        self.oauth_params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid",
            "marche_derive": "particulier",
            "state": state,
            "structure_id": self.structure_id,
            "nav_context": nav_context,
        }

        self.authorize.go(params=self.oauth_params)
        self.context.go(params=self.oauth_params)
        self.auth_username.go(params=self.oauth_params, json={"username": self.username})
        self.keypad.go(params=self.oauth_params)
        keypad_password = self.page.build_password(self.password)
        self.login_validation.go(
            params=self.oauth_params,
            json={"identifiant": self.username, "liste_touches": keypad_password},
        )
        if self.page.has_captcha():
            raise ActionNeeded(
                "Friendly captcha detected, please authenticate manually on the website once to disable it"
            )

        if not self.page.is_authenticated():
            raise BrowserIncorrectPassword()

        redirect_url = self.page.get_redirect_url()

        self.location(redirect_url)
        query = parse_qs(urlparse(redirect_url).query)
        self.security_login.go(
            params={
                "code": query.get("code", [None])[0],
                "state": query.get("state", [None])[0],
                "redirect_uri": redirect_uri,
            }
        )
        self._logged = True

    @need_login
    def iter_accounts(self):
        # La famille ASSURANCES (assurances dommages/protection juridique) est ignorée :
        # ses contrats réutilisent le numero_compte du compte de dépôt (collision d'id) et
        # n'ont pas de solde exploitable. Le set seen écarte les doublons inter-familles.
        seen = set()
        for family in ("COMPTES", "EPARGNE", "CREDITS", "PLACEMENTS"):
            self.accounts.go(params={"code_grande_famille": family})
            for account in self.page.iter_accounts(family=family):
                if account.id and account.id not in seen:
                    seen.add(account.id)
                    yield account

    def _open_detail_dav(self, account):
        # Second flux OAuth CA-Connect, propre au service detail-dav, amorcé par
        # un SSO côté espace-client avec l'identifiant du contrat.
        region = self.region
        contexte_specifique = {
            "numero_compte": account.id,
            "id_element_contrat": getattr(account, "_id_element_contrat", None),
        }
        self.sso.go(
            json={
                "id_parcours": "DETAIL-COMPTE-DAV",
                "nav_context": json.dumps({"contexte_specifique": contexte_specifique}),
            },
        )
        context_id = self.page.get_context_id()
        self.dav_fe.go(region=region, params={"sso": "AzCode", "context_id": context_id})
        # Ferme une éventuelle session detail-dav précédente, sinon le curseur
        # d'opérations reste sur le compte ouvert juste avant.
        self.dav_logout.go(region=region, data="")
        self.dav_user.go(region=region)
        state = self.page.get_state()
        client_id = self.dav_config.go(region=region).get_client_id()
        dav_redirect = f"{self.DETAILDAV}/{region}/fe/"
        self.authorize.go(
            params={
                "client_id": client_id,
                "redirect_uri": dav_redirect,
                "response_type": "code",
                "scope": "openid",
                "marche_derive": "particulier",
                "state": state,
            }
        )
        code = parse_qs(urlparse(self.url).query).get("code", [None])[0]
        self.dav_login.go(
            region=region,
            json={"code": code, "state": state, "redirectUrl": dav_redirect},
        )
        # Réarme le contexte du compte côté detail-dav avec le context_id du SSO :
        # sans cet appel, /operations/imputees renvoie 400 car la session re-loguée
        # ne sait pas quel compte interroger.
        self.dav_context.go(region=region, params={"contextId": context_id})

    @need_login
    def iter_history(self, account):
        if account.type != Account.TYPE_CHECKING and account.type != Account.TYPE_SAVINGS:
            return

        self._open_detail_dav(account)
        seen = set()
        for _ in range(self.MAX_HISTORY_CALLS):
            self.dav_operations.go(region=self.region)
            page = self.page
            fresh = 0
            for transaction in page.iter_history():
                if transaction.id in seen:
                    continue
                seen.add(transaction.id)
                fresh += 1
                yield transaction
            if not page.has_next() or not fresh:
                break

    @need_login
    def iter_coming(self, account):
        if account.type != Account.TYPE_CHECKING:
            return []

        self._open_detail_dav(account)
        self.dav_coming.go(region=self.region)
        return self.page.iter_coming()

    @need_login
    def iter_investment(self, account):
        # Non porté : nécessite un compte d'investissement (AV/PER) pour être
        # implémenté et testé sur la nouvelle API.
        return []
