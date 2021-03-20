import configparser
import requests
import os
import shutil
import sys
from enum import Enum
from pathlib import Path
import logging

logging.basicConfig(level=logging.WARNING, format='[%(asctime)s] [%(name)-12s] [%(levelname)-8s] %(message)s')
logger = logging


def parseEnumProto(url, name):
    r = requests.get(url)
    enumDict = {}
    found = False
    internalName = "enum {}".format(name)
    for line in r.iter_lines(decode_unicode=True):
        if not found:
            if internalName in line:
                found = True
            continue
        if not line.startswith("syntax") and not line.startswith("package") and "=" in line:
            enumDict[line.split("=")[0].strip()] = line.split("=")[1].replace(";", "").strip()
        if "}" in line:
            break
    enumDict = addEnumInfo(name, enumDict)
    resultingEnum = Enum(name.replace("Holo", ""), enumDict)
    globals()[name.replace("Holo", "")] = resultingEnum
    return resultingEnum



def addEnumInfo(name, enumDict):
    additionalInfo = configparser.ConfigParser()
    additionalInfo.read(os.path.dirname(os.path.abspath(__file__)) + "/additional-enum-info.ini")
    if name in additionalInfo:
        for elem in additionalInfo[name]:
            enumDict[elem.upper()] = additionalInfo[name][elem]
    return enumDict


def findIconFileName(mon, form, shiny=False):
    monPadded = str(f'{mon:0>3}')
    formPadded = str(f'{form:0>2}')
    if shiny:
        iconDir = str(Path.cwd()) + "/Telegram_hiRes_allShiny_withBorder"
    else:
        iconDir = str(Path.cwd()) + "/Telegram_hiRes_noShiny_withBorder"
    fullPath = "{}/pokemon_icon_{}_{}.webp".format(iconDir, monPadded, formPadded)
    if os.path.isfile(fullPath):
        return "pokemon_icon_{}_{}".format(monPadded, formPadded)
    elif formPadded == "00":
        logger.warning("Form 00 file not found ... why??")
    else:
        logger.warning("did not find file {} - fallback to 00 form".format(fullPath))
        return "pokemon_icon_{}_00".format(monPadded)


def copyAll(mon, form, shiny=False):
    filename = findIconFileName(mon, form, shiny=shiny)
    monPadded = str(f'{mon:0>3}')
    formPadded = str(f'{form:0>2}')
    folder = "allShiny" if shiny else "noShiny"
    filetypes = {}
    filetypes["Discord"] = "png"
    filetypes["Telegram"] = "webp"
    for receiver in ["Discord", "Telegram"]:
        source = "{}/{}_hiRes_{}_withBorder/{}.{}".format(Path.cwd(), receiver, folder, filename, filetypes[receiver])
        target = "{}/{}_hiRes_withShiny_withBorder/pokemon_icon_{}_{}.{}".format(Path.cwd(), receiver, monPadded,
                                                                                 formPadded, filetypes[receiver])
        logger.info("copy {} to {}".format(source, target))
        try:
            shutil.copyfile(source, target)
        except FileNotFoundError:
            logger.error("File {} not found, skipping.".format(source))


# get and process external data
PokemonId = parseEnumProto("https://raw.githubusercontent.com/Furtif/POGOProtos/master/base/base.proto",
                                      "HoloPokemonId")
Form = parseEnumProto("https://raw.githubusercontent.com/Furtif/POGOProtos/master/base/base.proto", "Form")


shinyPokemon = requests.get("https://pogoapi.net/api/v1/shiny_pokemon.json").json()
releasedPokemon = requests.get("https://pogoapi.net/api/v1/released_pokemon.json").json()
formList = [e.name for e in Form]

# create directories
for receiver in ["Telegram", "Discord"]:
    try:
        os.mkdir("{}/{}_hiRes_withShiny_withBorder".format(Path.cwd(), receiver))
    except Exception as e:
        logger.error("Failed creating directory {}_hiRes_withShiny_withBorder ({}). Please delete manually, I don't "
                     "want to screw up your storage.".format(receiver, e))
        sys.exit(1)


# loop over all released pokemon from pogoapi.net
for mon in releasedPokemon:
    thisMon = releasedPokemon[mon]
    name = thisMon["name"]

    # determine if mon and its alolan form can be caught from the wild
    if mon in shinyPokemon and shinyPokemon[mon]["found_wild"]:
        normalShiny = True
        if "alolan_shiny" in shinyPokemon[mon] and shinyPokemon[mon]["alolan_shiny"]:
            alolanShiny = True
        else:
            alolanShiny = False
    else:
        normalShiny = False
        alolanShiny = False
    shinyString = "as shiny" if normalShiny else "as non-shiny"

    # cleanup the name to match with Forms Enum
    remove = ["’", "♀", "♂", "."]
    cleanName = name.replace(" ", "_").replace("-", "_")
    for item in remove:
        cleanName = cleanName.replace(item, "")
    cleanName = cleanName.upper() + "_"
    logger.info("clean name: {}".format(cleanName))

    # create list of all forms of that mon
    possibleForms = []
    for form in formList:
        if cleanName in form:
            possibleForms.append(form)
    if not possibleForms:
        logger.warning("mon {} {} has no forms({})".format(mon, name, cleanName))
    logger.debug("forms for mon {} / {} : {}".format(mon, name, possibleForms))

    # copy the _00 file, then more according to forms
    copyAll(mon, 00, shiny=normalShiny)
    for form in possibleForms:
        if "ALOLA" in form and alolanShiny:
            logger.debug("create pokemon_icon_{}_{}.png as ALOLAN-shiny".format(mon, Form[form].value))
            filename = findIconFileName(mon, Form[form].value)
            copyAll(mon, Form[form].value, shiny=True)
        elif "ALOLA" in form:
            logger.debug("create pokemon_icon_{}_{}.png as ALOLAN-NON-shiny".format(mon, Form[form].value))
            copyAll(mon, Form[form].value)
        elif "SHADOW" in form or "PURIFIED" in form:
            # shadow and purified can't be wild, thus we don't need those icons ever
            continue
        else:
            logger.debug("create pokemon_icon_{}_{}.png {}".format(mon, Form[form].value, shinyString))
            copyAll(mon, Form[form].value, shiny=normalShiny)
