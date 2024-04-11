"""
mml2musicxml
"""

def __init__() -> None:
    """
    """

    import typing

    import lark
    import lark.visitors
    import lxml.etree as ET
    import pyokaka.okaka as okaka


    lark_grammar: str = """
        ?start: root

        root: channel_command? content (channel_command content)*

        content: command*

        ?command: call_command
            | define_command
            | note_command
            | key_command
            | length_command
            | loop_command
            | octave_command
            | octave_up_command
            | octave_down_command
            | octave_reverse_command
            | tempo_command
            | unsupported_command
        channel_command: ":" channel
        call_command: "{" name "}"
        define_command: "{" name "=" content "}"
        note_command: (rest | ("*" text ",")? step accidental?) length? dot* breath?
            | "N"i pitch ("," length dot*)? breath?
        key_command: "K"i key
        length_command: "L"i length
        loop_command: "[" content "]" count
        octave_command: "O"i octave
        octave_up_command: "<"
        octave_down_command: ">"
        octave_reverse_command: "!"
        tempo_command: "T"i tempo
        unsupported_command: /\|.+?\|/
            | /([PQV()&_]|@[DV])/i number?
            | /@(E|M[ALP])/i number "," number "," number "," number
            | /@(ER|M[ALP]?OF)/i
            | "$" /[0-7]/ ("=" number)?

        name: /[a-z0-9_]+/i
        text: /[a-z]+/i
        step: /[A-G]/i
        rest: /R/i
        accidental: /[#+-]/
        dot: "."
        breath: "//"

        channel: /(1[0-5]|[0-9])/
        count: /(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9][0-9]|[0-9])/
        key: /(-?(1[0-5]|[1-9])|0)/
        length: /(192|96|64|48|32|24|16|12|8|6|4|3|2|1)/
        number: /(-?[1-9][0-9]*|0)/
        octave: /(-1|[0-9])/
        pitch: /(12[0-7]|1[01][0-9]|[1-9][0-9]|[0-9])/
        tempo: /(102[0-3]|10[01][0-9]|[1-9][0-9]{1,2}|[1-9])/
        
        %ignore /\s+/
        %ignore /\/.+?\//
    """

    okaka.update_convert_dct({
        "cl": "っ",
        "q": "ん",
        "k": "く",
        "sh": "し’",
        "s": "す’",
        "ch": "ち’",
        "ts": "つ’",
        "t": "と’",
        "n": "ぬ’",
        "h": "ふ’",
        "f": "ふ’",
        "m": "む’",
        "y": "ゆ’",
        "r": "る’",
        "g": "ぐ’",
        "z": "ず’",
        "d": "ど’",
        "b": "ぶ’",
        "p": "ぷ’",
    })


    global run
    global Parser
    global Compiler
    global Pitch
    global Error
    global InternalError
    global ParsingError
    global CompilationError
    global MacroError
    global UndefinedMacroError
    global DuplicateMacroError

    Token = lark.Token
    Tree = lark.Tree

    channels = 16


    def run(
        program: str,
        *,
        encoding: str = "utf-8",
        minified: bool = False,
    ) -> list[str | None]:
        parser = Parser()
        tree = parser.parse(program)

        compiler = Compiler()
        scores = [
            ET.tostring(
                score,
                encoding=encoding,
                xml_declaration=True,
                pretty_print=not minified,
            ).decode(encoding)
            if score is not None else None
            for score in compiler.compile(tree)
        ]

        return scores


    class Parser:
        def __init__(self) -> None:
            self.__lark: typing.Final = lark.Lark(lark_grammar)

        def parse(self, program: str) -> Tree:
            try:
                return self.__lark.parse(program)

            except lark.UnexpectedInput as e:
                raise ParsingError("Incorrect MML", line=e.line, column=e.column)

            except lark.LarkError:
                raise InternalError("Internal error")


    class Compiler(lark.visitors.Interpreter):
        def __init__(self) -> None:
            self.__scores: list[ET.Element | None] = [None] * channels
            self.__parts: list[ET.Element | None] = [None] * channels

            self.__channel: int
            self.__local: bool

            self.__key: int
            self.__length: int
            self.__octave: int
            self.__tempo: int

            self.__initial_key: int = 0
            self.__initial_length: int = 4
            self.__initial_octave: int = 4
            self.__initial_tempo: int = 120

            self.__macros: dict[str, Tree] = {}

            self.__octave_reverse: bool = False

            self.__previous_notations: ET.Element | None = None
            self.__previous_pitch: Pitch | None = None
            self.__previous_text: str | None = None

            self.__init_channel(0, local=False)

        def __init_channel(self, channel: int, *, local: bool = True) -> None:
            self.__channel = channel
            self.__local = local

            score = ET.Element("score-partwise")
            part = ET.SubElement(score, "part")
            
            self.__scores[self.__channel] = score
            self.__parts[self.__channel] = part

            self.__key = self.__initial_key
            self.__length = self.__initial_length
            self.__octave = self.__initial_octave
            self.__tempo = self.__initial_tempo

        def compile(self, tree: Tree):
            self.visit(tree)

            return self.__scores

        def call_command(self, tree: Tree) -> None:
            name = str(tree.children[0].children[0])
            normalized_name = name.upper()

            if normalized_name not in self.__macros:
                raise UndefinedMacroError(name=name)

            content = self.__macros[normalized_name]

            previous_length = self.__length
            previous_octave = self.__octave

            self.visit(content)

            self.__length = previous_length
            self.__octave = previous_octave

        def channel_command(self, tree: Tree) -> None:
            self.__channel = int(tree.children[0].children[0])
            self.__local = True

            self.__init_channel()

        def define_command(self, tree: Tree) -> None:
            name = str(tree.children[0].children[0])
            normalized_name = name.upper()
            content = tree.children[1]

            if normalized_name in self.__macros:
                raise DuplicateMacroError(name=name)

            self.__macros[normalized_name] = content

        def key_command(self, tree: Tree) -> None:
            self.__key = int(tree.children[0].children[0])

            if not self.__local:
                self.__global_key = self.__key

        def length_command(self, tree: Tree) -> None:
            self.__length = int(tree.children[0].children[0])

        def loop_command(self, tree: Tree) -> None:
            content = tree.children[0]
            count = int(tree.children[1].children[0])

            for _ in range(count):
                previous_octave = self.__octave

                self.visit(content)

                self.__octave = previous_octave

        def note_command(self, tree: Tree) -> None:
            rest: bool = False
            text: str = ""
            step: str = ""
            alter: int = 0
            pitch: Pitch = Pitch(0)
            length: int = self.__length
            dot: int = 0
            breath: bool = False
            tie: bool = False

            for subtree in tree.children:
                match subtree.data:
                    case "rest":
                        rest = True

                    case "text":
                        text = subtree.children[0]

                    case "step":
                        step = str(subtree.children[0])

                    case "accidental":
                        if subtree.children[0] == "-":
                            alter = -1
                        else:
                            alter = +1

                    case "pitch":
                        pitch.value = int(subtree.children[0])

                    case "length":
                        length = int(subtree.children[0])

                    case "dot":
                        dot += 1

                    case "breath":
                        breath = True

            if not rest:
                if step:
                    pitch.step = step
                    pitch.alter = alter
                    pitch.octave = self.__octave

                pitch.value += self.__key

                step = pitch.step
                alter = pitch.alter
                octave = pitch.octave
                
                if self.__previous_notations:
                    if self.__previous_pitch:
                        if self.__previous_text:
                            if self.__previous_text.endswith(text):
                                tie = True

                self.__previous_pitch = pitch
                self.__previous_text = text

            beat = 2 * (2 ** dot) - 1
            beat_type = length * (2 ** dot)

            measure = ET.SubElement(self.__parts[self.__channel], "measure")

            attributes = ET.SubElement(measure, "attributes")

            ET.SubElement(attributes, "divisions").text = "1"

            key = ET.SubElement(attributes, "key")
            ET.SubElement(key, "fifths").text = "0"

            time = ET.SubElement(attributes, "time")
            ET.SubElement(time, "beats").text = str(beat)
            ET.SubElement(time, "beat-type").text = str(beat_type)

            clef = ET.SubElement(attributes, "clef")
            ET.SubElement(clef, "sign").text = "G"
            ET.SubElement(clef, "line").text = "2"

            ET.SubElement(attributes, "sound", tempo=str(self.__tempo))

            note = ET.SubElement(measure, "note")

            ET.SubElement(note, "duration").text = str(beat)

            if not rest:
                pitch = ET.SubElement(note, "pitch")
                ET.SubElement(pitch, "step").text = step
                ET.SubElement(pitch, "alter").text = str(alter)
                ET.SubElement(pitch, "octave").text = str(octave)

                notations = ET.SubElement(note, "notations")
                articulations = ET.SubElement(notations, "articulations")

                if text:
                    lyric = ET.SubElement(note, "lyric")
                    ET.SubElement(lyric, "text").text = okaka.convert(text)

                if breath:
                    ET.SubElement(articulations, "breath-mark")

                if tie:
                    previous_notations = self.__previous_notations

                    ET.SubElement(previous_notations, "tie", type="start")
                    ET.SubElement(notations, "tie", type="stop")

                self.__previous_notations = notations

            else:
                ET.SubElement(note, "rest")

                self.__previous_notations = None
                self.__previous_pitch = pitch
                self.__previous_text = None

        def octave_command(self, tree: Tree) -> None:
            self.__octave = int(tree.children[0].children[0])

        def octave_up_command(self, tree: Tree) -> None:
            if self.__octave_reverse:
                self.__octave -= 1

            else:
                self.__octave += 1

        def octave_down_command(self, tree: Tree) -> None:
            if self.__octave_reverse:
                self.__octave += 1

            else:
                self.__octave -= 1

        def octave_reverse_command(self, tree: Tree) -> None:
            self.__octave_reverse = True

        def tempo_command(self, tree: Tree) -> None:
            self.__tempo = int(tree.children[0].children[0])

            if not self.__local:
                self.__global_tempo = self.__tempo

        def unsupported_command(self, tree: Tree) -> None:
            pass

        def __default__(self, tree: Tree | Token) -> None:
            if not isinstance(tree, lark.Tree):
                return

            for subtree in tree.children:
                self.visit(subtree)


    class Pitch:
        def __init__(
            self,
            value: int | None,
            *,
            step: str | None = None,
            alter: int | None = None,
            octave: int | None = None,
        ) -> None:
            self.__step: str
            self.__alter: int
            self.__octave: int

            if value is not None:
                self.value = value

            else:
                self.step = step
                self.alter = alter
                self.octave = octave


        @property
        def value(self) -> int:
            value = 0

            value += [9, 11, 0, 2, 4, 5, 7][ord(self.step) - 0x41]
            value += self.alter
            value += (self.octave + 1) * 12

            value = min(max(value, 0), 127)

            return value

        @value.setter
        def value(self, value: int) -> None:
            self.step = [
                "C", "C", "D", "D", "E", "F",
                "F", "G", "G", "A", "A", "B",
            ][value % 12]

            self.alter = [
                0, 1, 0, 1, 0, 0,
                1, 0, 1, 0, 1, 0,
            ][value % 12]

            self.octave = value // 12 - 1

        @property
        def step(self) -> str:
            return self.__step

        @step.setter
        def step(self, step: str) -> None:
            step = step.upper()

            if step not in ("C", "D", "E", "F", "G", "A", "B"):
                raise InternalError("Illegal step string")

            self.__step = step

        @property
        def alter(self) -> int:
            return self.__alter

        @alter.setter
        def alter(self, alter: int) -> None:
            self.__alter = alter % 12

            if alter < 0:
                self.__alter -= 12

        @property
        def octave(self) -> int:
            return self.__octave

        @octave.setter
        def octave(self, octave: int) -> None:
            self.__octave = min(max(octave, -1), 9)


    class Error(Exception):
        default_message: str | None = None

        def __init__(
            self,
            message: str | None = None,
            **info,
        ):
            super().__init__(message or self.__class__.default_message.format(**info))


    class InternalError(Error):
        pass


    class ParsingError(Error):
        def __init__(
            self,
            message: str | None = None,
            *,
            line: int,
            column: int,
        ):
            super().__init__(message, line=line, column=column)

            self.line: typing.Final = line
            self.column: typing.Final = column


    class CompilationError(Error):
        pass


    class MacroError(CompilationError):
        def __init__(
            self,
            message: str | None = None,
            *,
            name: str,
        ):
            super().__init__(message, name=name)

            self.name: typing.Final = name


    class UndefinedMacroError(MacroError):
        default_message = "Undefined macro '{name}'"


    class DuplicateMacroError(MacroError):
        default_message = "Duplicate macro '{name}'"


__init__()

del __init__
