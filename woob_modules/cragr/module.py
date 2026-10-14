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

from collections import OrderedDict

from woob.capabilities.bank import CapBank
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value, ValueBackendPassword

from .browser import CreditAgricoleBrowser


__all__ = ["CreditAgricoleModule"]


class CreditAgricoleModule(Module, CapBank):
    NAME = "cragr"
    MAINTAINER = "Quentin Defenouillère"
    EMAIL = "quentin.defenouillere@budget-insight.com"
    VERSION = "3.7"
    DESCRIPTION = "Crédit Agricole"
    LICENSE = "LGPLv3+"

    region_choices = {
        "www.ca-alpesprovence.fr": "Alpes Provence",
        "www.ca-alsace-vosges.fr": "Alsace-Vosges",
        "www.ca-anjou-maine.fr": "Anjou Maine",
        "www.ca-aquitaine.fr": "Aquitaine",
        "www.ca-atlantique-vendee.fr": "Atlantique Vendée",
        "www.ca-briepicardie.fr": "Brie Picardie",
        "www.ca-cb.fr": "Champagne Bourgogne",
        "www.ca-centrefrance.fr": "Centre France",
        "www.ca-centreloire.fr": "Centre Loire",
        "www.ca-centreouest.fr": "Centre Ouest",
        "www.ca-centrest.fr": "Centre Est",
        "www.ca-charente-perigord.fr": "Charente Périgord",
        "www.ca-cmds.fr": "Charente-Maritime Deux-Sèvres",
        "www.ca-corse.fr": "Corse",
        "www.ca-cotesdarmor.fr": "Côtes d'Armor",
        "www.ca-des-savoie.fr": "Des Savoie",
        "www.ca-finistere.fr": "Finistere",
        "www.ca-franchecomte.fr": "Franche-Comté",
        "www.ca-guadeloupe.fr": "Guadeloupe",
        "www.ca-illeetvilaine.fr": "Ille-et-Vilaine",
        "www.ca-languedoc.fr": "Languedoc",
        "www.ca-loirehauteloire.fr": "Loire Haute Loire",
        "www.ca-lorraine.fr": "Lorraine",
        "www.ca-martinique.fr": "Martinique Guyane",
        "www.ca-morbihan.fr": "Morbihan",
        "www.ca-nmp.fr": "Nord Midi-Pyrénées",
        "www.ca-nord-est.fr": "Nord Est",
        "www.ca-norddefrance.fr": "Nord de France",
        "www.ca-normandie-seine.fr": "Normandie Seine",
        "www.ca-normandie.fr": "Normandie",
        "www.ca-paris.fr": "Ile-de-France",
        "www.ca-pca.fr": "Provence Côte d'Azur",
        "www.ca-reunion.fr": "Réunion",
        "www.ca-sudmed.fr": "Sud Méditerranée",
        "www.ca-sudrhonealpes.fr": "Sud Rhône Alpes",
        "www.ca-toulouse31.fr": "Toulouse 31",
        "www.ca-tourainepoitou.fr": "Tourraine Poitou",
        "www.ca-valdefrance.fr": "Val de France",
        "www.ca-pyrenees-gascogne.fr": "Pyrénées Gascogne",
    }
    region_choices = OrderedDict(
        [(website, f"{region} ({website})") for website, region in sorted(region_choices.items())]
    )

    region_aliases = {
        "m.ca-alpesprovence.fr": "www.ca-alpesprovence.fr",
        "m.ca-alsace-vosges.fr": "www.ca-alsace-vosges.fr",
        "m.ca-anjou-maine.fr": "www.ca-anjou-maine.fr",
        "m.ca-aquitaine.fr": "www.ca-aquitaine.fr",
        "m.ca-atlantique-vendee.fr": "www.ca-atlantique-vendee.fr",
        "m.ca-briepicardie.fr": "www.ca-briepicardie.fr",
        "m.ca-cb.fr": "www.ca-cb.fr",
        "m.ca-centrefrance.fr": "www.ca-centrefrance.fr",
        "m.ca-centreloire.fr": "www.ca-centreloire.fr",
        "m.ca-centreouest.fr": "www.ca-centreouest.fr",
        "m.ca-centrest.fr": "www.ca-centrest.fr",
        "m.ca-charente-perigord.fr": "www.ca-charente-perigord.fr",
        "m.ca-cmds.fr": "www.ca-cmds.fr",
        "m.ca-corse.fr": "www.ca-corse.fr",
        "m.ca-cotesdarmor.fr": "www.ca-cotesdarmor.fr",
        "m.ca-des-savoie.fr": "www.ca-des-savoie.fr",
        "m.ca-finistere.fr": "www.ca-finistere.fr",
        "m.ca-franchecomte.fr": "www.ca-franchecomte.fr",
        "m.ca-guadeloupe.fr": "www.ca-guadeloupe.fr",
        "m.ca-illeetvilaine.fr": "www.ca-illeetvilaine.fr",
        "m.ca-languedoc.fr": "www.ca-languedoc.fr",
        "m.ca-loirehauteloire.fr": "www.ca-loirehauteloire.fr",
        "m.ca-lorraine.fr": "www.ca-lorraine.fr",
        "m.ca-martinique.fr": "www.ca-martinique.fr",
        "m.ca-morbihan.fr": "www.ca-morbihan.fr",
        "m.ca-nmp.fr": "www.ca-nmp.fr",
        "m.ca-nord-est.fr": "www.ca-nord-est.fr",
        "m.ca-norddefrance.fr": "www.ca-norddefrance.fr",
        "m.ca-normandie-seine.fr": "www.ca-normandie-seine.fr",
        "m.ca-normandie.fr": "www.ca-normandie.fr",
        "m.ca-paris.fr": "www.ca-paris.fr",
        "m.ca-pca.fr": "www.ca-pca.fr",
        "m.ca-reunion.fr": "www.ca-reunion.fr",
        "m.ca-sudmed.fr": "www.ca-sudmed.fr",
        "m.ca-sudrhonealpes.fr": "www.ca-sudrhonealpes.fr",
        "m.ca-toulouse31.fr": "www.ca-toulouse31.fr",
        "m.ca-tourainepoitou.fr": "www.ca-tourainepoitou.fr",
        "m.ca-valdefrance.fr": "www.ca-valdefrance.fr",
        "m.lefil.com": "www.ca-pyrenees-gascogne.fr",
    }

    BROWSER = CreditAgricoleBrowser

    CONFIG = BackendConfig(
        Value("website", label="Caisse Régionale", choices=region_choices, aliases=region_aliases),
        ValueBackendPassword("login", label="Identifiant à 11 chiffres", masked=False, regexp=r"\d{11}"),
        ValueBackendPassword("password", label="Code personnel à 6 chiffres", regexp=r"\d{6}"),
    )

    def create_default_browser(self):
        return self.create_browser(
            self.config["website"].get(),
            self.config["login"].get(),
            self.config["password"].get(),
        )

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_coming(self, account):
        return self.browser.iter_coming(account)
