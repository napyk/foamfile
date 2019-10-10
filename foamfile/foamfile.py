import os
import re
import pyparsing as pp
from collections import OrderedDict


class FoamFile:
    def __init__(self, path, mode="r", foam_class=None):
        self.mode = mode
        self.path = path
        self.header = OrderedDict([
            ("version", 2.0),
            ("format", "ascii"),
            ("object", os.path.basename(self.path)),
            ("class", foam_class)
        ])
        self.file = None
        self.startcomment = [
            "/*--------------------------------*- C++ -*----------------------------------*\\",
            "  =========                   |",
            "  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox",
            "   \\\\    /   O peration     | Website:  https://openfoam.org",
            "    \\\\  /    A nd           | Version:  6",
            "     \\\\/     M anipulation  |",
            "\*---------------------------------------------------------------------------*/\n"
        ]
        self.spacer = ["\n// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //\n"]
        self.endcomment = ["\n// ************************************************************************* //\n"]

    def __enter__(self):
        self.file = open(self.path, self.mode)
        return self

    def __exit__(self, *args, **kwargs):
        self.file.close()

    def removeComments(self, string):
        # /* COMMENT */
        # pp.cStyleComment
        string = re.sub(re.compile("/\*.*?\*/", re.DOTALL), "", string)
        # // COMMENT
        # pp.dblSlashComment
        string = re.sub(re.compile("//.*?\n"), "", string)
        return string

    def from_foam(self, text):
        enclosed_dict = pp.Forward()
        enclosed_list = pp.Forward()

        odict = lambda key, value: pp.ZeroOrMore(pp.Group(key + value)).setParseAction(
            lambda toks: OrderedDict(toks.asList()))

        custom_alphanums = pp.alphanums + "_:.#$*/,<>"

        enclosed_function = pp.Forward()
        function = "(" + pp.ZeroOrMore(pp.Word(custom_alphanums) | enclosed_function) + ")"
        named_function = (pp.Combine(pp.Word(custom_alphanums) + "(" + pp.ZeroOrMore(pp.Word(custom_alphanums) | function) + ")")).setParseAction("".join)
        enclosed_function << function

        custom_quoted_string = ("\"" + pp.OneOrMore(pp.Word(custom_alphanums + "|()")).setParseAction(" ".join) + "\"").setParseAction("".join)

        dictionary_key = named_function | pp.Word(custom_alphanums) | custom_quoted_string
        dictionary_key_value = odict(dictionary_key, enclosed_dict)

        dictionary_object = pp.Suppress("{") + dictionary_key_value + pp.Suppress("}")
        named_dictionary_object = odict(pp.Word(custom_alphanums), dictionary_object) + pp.Suppress(pp.Optional(";"))

        list_object = (pp.Suppress("(") + pp.ZeroOrMore(
            pp.Group(pp.delimitedList(enclosed_list, delim=pp.White()))) + pp.Suppress(")")).setParseAction(
            lambda toks: toks if toks else [[]])
        # TODO add token identifier
        named_list_object = odict(pp.Word(custom_alphanums), list_object + pp.Suppress(";"))

        # directives
        # TODO #include filename
        # directive = pp.Regex("#([^\s]+)") + custom_quoted_string

        # (1.0 1.1 1.2)
        vector = "(" + pp.pyparsing_common.number * 3 + ")"

        # # [0 2 -1 0 0 0 0]
        # # [Mass Length Time Temperature Quantity Current Luminous intensity]
        dimensionSet = (pp.Suppress("[") + pp.delimitedList(pp.pyparsing_common.number * 7,
                                                            delim=pp.White()) + pp.Suppress("]")).setParseAction(
            lambda toks: "[" + " ".join([str(i) for i in toks]) + "]")

        # field
        field_value = (pp.oneOf("uniform nonuniform") + (pp.pyparsing_common.number | vector)).setParseAction(
            lambda toks: " ".join([str(i) for i in toks]))

        enclosed_dict << (
                ((pp.OneOrMore(named_function | field_value | dimensionSet | pp.pyparsing_common.number | pp.Word(
                    custom_alphanums)).setParseAction(
                    lambda toks: " ".join([str(i) for i in toks]) if len(toks) > 1 else toks[
                        0]) | custom_quoted_string | list_object) + pp.Suppress(
                    ";")) | custom_quoted_string | (
                        dictionary_object + pp.Suppress(pp.Optional(";"))))
        enclosed_list << (
                pp.pyparsing_common.number | list_object | pp.Word(custom_alphanums) | dictionary_object)

        combined = dictionary_key_value | named_list_object | named_dictionary_object

        return combined.searchString(text)[0][0]

    def read(self):
        if self.file is None:
            self.file = open(self.path, self.mode)
        text = self.file.read()
        text = self.removeComments(text)
        text = self.from_foam(text)
        if next(iter(text)) == "FoamFile":
            self.header = text.popitem(last=False)[1]
        return text

    def to_foam(self, foam_object, level=0, maxlength=50):
        lines = []
        if type(foam_object) in (list, tuple):
            for list_entry in foam_object:
                if type(list_entry) in (list, tuple):
                    lines.append("\t" * level + "(" + " ".join(self.to_foam(list_entry, 0)) + ")")
                elif type(list_entry) in (dict, OrderedDict):
                    lines.append("\t" * level + "{")
                    lines += self.to_foam(list_entry, level + 1)
                    lines.append("\t" * level + "}")
                else:
                    lines.append("\t" * level + str(list_entry))
        elif type(foam_object) in (dict, OrderedDict):
            if len(foam_object) > 0:
                tab_expander = max([len(i) for i in foam_object if type(i) is str]) + 1
            for key, value in foam_object.items():
                if type(value) in (dict, OrderedDict):
                    lines += ["\t" * level + f"{key}", "\t" * level + "{"]
                    lines += self.to_foam(value, level + 1)
                    lines.append("\t" * level + "}")
                elif type(value) in (list, tuple):
                    lines += ["\t" * level + f"{key}", "\t" * level + "("]
                    lines += self.to_foam(value, level + 1)
                    lines.append("\t" * level + ");")
                else:
                    if key in ["#include", "#includeIfPresent", "#includeEtc", "#includeFunc", "#remove"]:
                        lines.append("\t" * level + str(key).ljust(tab_expander) + str(value))
                    else:
                        lines.append("\t" * level + str(key).ljust(tab_expander) + str(value) + ";")
        return lines

    def write(self, content):
        if self.file is None:
            self.file = open(self.path, self.mode)
        os.makedirs(os.path.abspath(os.path.dirname(self.path)), exist_ok=True)
        self.file.write("\n".join(
            self.startcomment + self.to_foam({"FoamFile": self.header}) + self.spacer + self.to_foam(
                content) + self.endcomment))

    def close(self):
        self.file.close()
