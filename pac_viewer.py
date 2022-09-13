import copy
import csv
import io
import struct
from dataclasses import dataclass
from enum import Enum, Flag, auto
from io import BytesIO
from pathlib import Path
from struct import unpack
from typing import Any, Dict, List, Tuple, Union

# from numba import jit
import typer
from rich import print


class Game(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class InstType(Flag):
    INT = auto()
    UINT = auto()
    FLOAT = auto()
    STR = auto()
    P = auto()
    T = auto()
    V = auto()
    BYTES = auto()
    COUNT = auto()
    CONTINOUS = auto()
    ENTITY_ID = auto()
    EQUIP_ID = auto()
    KEYBIND_ID = auto()
    LOOT_ID = auto()

    @classmethod
    def value_of(cls, value):
        for k, v in cls.__members__.items():
            if k == value.upper():
                return v


@dataclass
class InstParam:
    name: str = None
    type: InstType = None
    type_str: str = None
    value: Any = None

    @property
    def name_var(self):
        return self.name.lower().replace(" ", "_")


@dataclass
class Instruction:
    type_id: int = None
    type_subid: int = None
    type_name: str = None
    desc: str = None
    params: List[InstParam] = None
    offset: int = None


def get_ids(csv_path: Path) -> Dict[int, str]:
    ids: Dict[int, str] = {}
    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        r = csv.reader(csvfile, delimiter=";")
        for (
            id_col,
            name_col,
        ) in r:
            ids[int(id_col, 16)] = name_col.replace(" ", "_").upper()
    return ids


def get_instruction_set(file_path="p2_instruction_set.csv") -> List[Instruction]:
    instructions_set: List[Instruction] = []
    with open(file_path, newline="", encoding="utf-8") as csvfile:
        r = csv.reader(csvfile, delimiter=";")
        for (
            type_id_col,
            type_subid_col,
            type_name_col,
            desc_col,
            params_col,
        ) in r:
            params: List[InstParam] = []
            if params_col != "":
                for p in params_col.split(","):
                    param: InstParam = InstParam()
                    p_list = p.split(":")
                    param.name = p_list[0].strip()
                    param.type_str = p_list[1].strip().upper()
                    type = None
                    if "UINT" in param.type_str:
                        type = InstType.UINT
                    elif "INT" in param.type_str:
                        type = InstType.INT
                    elif "FLOAT" in param.type_str:
                        type = InstType.FLOAT
                    elif "STR" in param.type_str:
                        type = InstType.STR
                    elif param.type_str.startswith("T_"):
                        type = InstType.T
                    elif param.type_str.startswith("V_"):
                        type = InstType.V
                    elif "KEYBIND_ID" in param.type_str:
                        type = InstType.KEYBIND_ID
                    elif "ENTITY_ID" in param.type_str:
                        type = InstType.ENTITY_ID
                    elif "EQUIP_ID" in param.type_str:
                        type = InstType.EQUIP_ID
                    elif "LOOT_ID" in param.type_str:
                        type = InstType.LOOT_ID
                    else:
                        print(f"Invalid type: {param.type_str }")
                        exit(1)
                    if "_P" in param.type_str:
                        type |= InstType.P
                    elif "COUNT_" in param.type_str:
                        type |= InstType.COUNT
                    elif "CONTINOUS_" in param.type_str:
                        type |= InstType.CONTINOUS

                    param.type = type
                    params.append(param)
            inst = Instruction(
                type_id=int(type_id_col, 16),
                type_subid=int(type_subid_col, 16),
                type_name=type_name_col,
                desc=desc_col,
                params=params,
            )
            # print(f"{inst}\n")
            instructions_set.append(inst)
        # exit()
    return instructions_set


def get_last_offset(infile) -> int:
    current_offset = infile.tell()
    infile.seek(0, io.SEEK_END)
    last_offset = infile.tell()
    infile.seek(current_offset)
    return last_offset


def get_inst_raw_bytes(infile, last_offset: int) -> bytearray:
    raw_bytes = bytearray(infile.read(4))
    # print("-")
    if infile.tell() < last_offset:
        raw_4_bytes = infile.read(4)
        inst_magic, inst_id, inst_subid = unpack("BBH", raw_4_bytes)
        if infile.tell() == last_offset:
            raw_bytes.extend(raw_4_bytes)
        else:
            # i = 1
            # while inst_magic != 0x25 and inst_subid != 0x00 and infile.tell() < last_offset:
            while infile.tell() < last_offset:
                # print(f"{i}")
                # i += 1
                # TODO First get size looking at instructions_set.csv
                # TODO fix addResultInfoValueMessage offset 0x21820 in DATA_CMN\actor\mission\missionid_10430.bnd\missiondata.bnd\missionscript.pac
                if (
                    inst_magic == 0x25
                    and inst_id < 0x22
                    and inst_subid != 0x00
                    and inst_subid < 0x2400
                ):
                    break
                raw_bytes.extend(raw_4_bytes)
                raw_4_bytes = infile.read(4)
                inst_magic, inst_id, inst_subid = unpack("BBH", raw_4_bytes)
            # if infile.tell() == last_offset:
            #     raw_bytes.extend(raw_4_bytes)
            # else:
            # if len(raw_bytes) > 4:
            infile.seek(infile.tell() - 4)
            # print (f"{infile.tell():08X}")
    # print (" ".join([f"{b:02X}" for b in raw_bytes]))
    return raw_bytes


def get_str_params(params: List[InstParam]) -> str:
    # return ",".join(str(p) for p in params)
    str_params = ""
    for p in params:
        if p.type_str.startswith("T_"):
            continue
        if InstType.COUNT in p.type:
            # str_params += f"{p.name_var}={p.value:X}"
            continue
        str_params += ", " if str_params != "" else ""

        if InstType.INT in p.type or InstType.UINT in p.type:
            str_params += f"{p.name_var}={p.value:X}"
        elif InstType.KEYBIND_ID in p.type:
            try:
                str_params += f"KB_{keybinds[p.value]}"
            except KeyError:
                str_params += f"{p.name_var}=KB_{p.value:X}"
        elif InstType.ENTITY_ID in p.type:
            try:
                # str_params += f"ENT_{entities[p.value]}"
                str_params += f"{p.name_var}=ENT_{p.value:X}"
            except KeyError:
                str_params += f"{p.name_var}=ENT_{p.value:X}"
        elif InstType.EQUIP_ID in p.type:
            try:
                # str_params += f"EQP_{equipment[p.value]}"
                str_params += f"{p.name_var}=EQP_{p.value:X}"
            except KeyError:
                str_params += f"{p.name_var}=EQP_{p.value:X}"
        elif InstType.LOOT_ID in p.type:
            try:
                str_params += f"LOOT_{loot[p.value]}"
                # str_params += f"{p.name_var}=LOOT_{p.value:X}"
            except KeyError:
                str_params += f"{p.name_var}=LOOT_{p.value:X}"
        elif InstType.FLOAT in p.type:
            # str_params += f"{p.value:3f}"
            str_params += f"{p.name_var}={p.value}"
        elif InstType.STR in p.type:
            str_params += f'{p.name_var}="{p.value}"'
            # str_params += " ".join([f"{b:02X}" for b in p.value])
        elif p.type_str.startswith("T_"):
            str_params += f"{p.name_var}={p.value:X}"
        elif InstType.BYTES in p.type:
            str_params += " ".join([f"{b:02X}" for b in p.value])
        else:
            # str_params += f"{p.value}"
            print(f"{params} {p.type}")
            exit()

    return str_params


def print_new_types(instructions: List[Union[Instruction, Tuple[int, bytearray]]]):
    inst_sizes = set()
    for i, inst in enumerate(instructions):
        if isinstance(inst, Tuple):
            continue
        if "unk_" in inst.type_name:
            # inst_sizes.add(inst.type_name, len(inst.params[0].value))
            inst_sizes.add(
                (
                    inst.type_id,
                    inst.type_subid,
                    len(inst.params[0].value),
                )
            )

    inst_sizes_dict = {}
    for i_id, i_subid, s in sorted(inst_sizes):
        # print(f"{i}: {s}")
        i = f"{i_id:02X} {i_subid:04X}"
        try:
            if inst_sizes_dict[i]:
                inst_sizes_dict[i] = -1
        except KeyError:
            inst_sizes_dict[i] = s
        # exit()

    for i, s in inst_sizes_dict.items():
        # print(f"{i}: {s}")
        if s == -1:
            continue
        string = f"{i.replace(' ', ';')};{i.replace(' ', '_')};Unk;"
        for i in range(s // 4):
            string += f"Unk{i+1}: uint, "
        if s > 0:
            string = string[:-2]
        print(string)


app = typer.Typer()


# @jit()
@app.command()
def pac(
    input: Path = typer.Argument(..., help="PAC file path"),
    game: Game = typer.Option(Game.P3, case_sensitive=False, help="Patapon game"),
    # output: Path = typer.Option(None, "--output", "-o", help="TXT file path"),
):
    # if not input.is_file():
    #     print("Invalid PAC file path")
    #     exit(1)
    # if not output:
    #     output = input.parent.joinpath(f"{input.stem}.txt")
    pac_list: List[Path] = []
    if input.is_file():
        pac_list.append(input)
    else:
        # pac_list.extend(list(input.glob("**/stagescript.pac")))
        # pac_list.extend(list(input.glob("**/missionscript.pac")))
        pac_list.extend(list(input.glob("**/*.pac")))

    instructions_set = get_instruction_set(f"{game.value.lower()}_instruction_set.csv")
    keybinds = get_ids(Path("./keybinds.csv"))
    loot = get_ids(Path(f"./{game.value.lower()}_loot.csv"))

    for input in pac_list:
        output = input.parent.joinpath(f"{input.stem}.txt")
        # print(f'Reading "{input}"')
        infile = open(input, "rb")
        # outfile = open(output, "w", encoding="utf-8")
        last_offset = get_last_offset(infile)

        instructions: List[Union[Instruction, Tuple[int, bytearray]]] = []

        while infile.tell() < last_offset:
            offset = infile.tell()
            raw_bytes = get_inst_raw_bytes(infile, last_offset)
            # exit()
            # raw_bytes_str = " ".join([f"{b:02X}" for b in raw_bytes])
            params_bytes = raw_bytes[4:]
            params_io = BytesIO(params_bytes)
            inst_magic, inst_id, inst_subid = unpack("BBH", raw_bytes[0:4])
            # print (len(params_bytes))
            # exit()
            if inst_magic != 0x25:
                if len(instructions) > 0 and isinstance(instructions[-1], Tuple):
                    instructions[-1][1].extend(raw_bytes)
                else:
                    instructions.append((offset, raw_bytes))
            else:
                inst = Instruction(
                    type_id=inst_id,
                    type_subid=inst_subid,
                    type_name=f"unk_{inst_id:02X}_{inst_subid:04X}",
                    desc="Unk",
                    # size_bytes_params=-1,
                    params=[
                        InstParam(name=None, type=InstType.BYTES, type_str="bytes")
                    ],
                )
                for i in instructions_set:
                    if i.type_id == inst_id and i.type_subid == inst_subid:
                        # inst = i
                        inst = copy.deepcopy(i)
                inst.offset = offset
                # if inst_magic != 0x25 and infile.tell() < last_offset:
                # outfile.write(f"{offset:08X} {raw_bytes_io}\n")
                # raw_bytes_parsed = 0
                # while raw_bytes_parsed <len(params_bytes):
                # if len(inst.params) == 1 and inst.params[0].type == InstType.BYTES:
                # inst.params[0].value = params_bytes
                # print (f"{offset:08X}")

                try:

                    for i in range(len(inst.params)):
                        param: InstParam = inst.params[i]
                        if param.type == InstType.BYTES:
                            param.value = params_bytes
                        elif param.type == InstType.STR:
                            # # text = params_io.read(4)
                            # text = unpack("4s", params_io.read(4))[0].decode("shift_jis")
                            # while text[-1] != "\x00":
                            #     text += unpack("4s", params_io.read(4))[0].decode("shift_jis")
                            params_last_offset = get_last_offset(params_io)
                            text_bytes = params_io.read(1)
                            while (
                                text_bytes[-1] != 0x00
                                and params_io.tell() < params_last_offset
                            ):
                                text_bytes += params_io.read(1)
                                # print(f"{infile.tell():08X}")
                                # print(text_bytes[-1])
                            # text = unpack(f"{len(text_bytes)}s", bytearray(text_bytes))[0].decode("cp932").rstrip("\x00")
                            text = (
                                unpack(f"{len(text_bytes)}s", bytearray(text_bytes))[0]
                                .decode("shift_jis")
                                .rstrip("\x00")
                            )
                            if (
                                i == len(inst.params) - 1
                            ):  # read variables if str is the last parameter
                                text_variables = params_io.read()
                                # if len(text_variables) > 0:
                                #     if len(text_variables) >= 4:
                                #         text += "{"
                                #         chunks = [
                                #             text_variables[i : i + 4]
                                #             for i in range(0, len(text_variables), 4)
                                #         ]
                                #         chunk_count = 0
                                #         for chunk in chunks:
                                #             if len(chunk) == 4:
                                #                 # if chunk != b"\x00" * 4:
                                #                 # text += " ".join([f"{b:02X}" for b in chunk])
                                #                 text += " " if chunk_count > 0 else ""
                                #                 text += f"{unpack(f'I', chunk)[0]:08X}"
                                #                 chunk_count += 1
                                #             elif chunk != b"\x00" * len(chunk):
                                #                 print("Error 1. Expecting padding")
                                #                 exit()
                                #         text += "}"
                                #         # text += (
                                #         #     "{" + " ".join([f"{b:02X}" for b in text_variables]) + "}"
                                #         # )
                                #     elif text_variables != b"\x00" * len(text_variables):
                                #         print("Error 2. Expecting padding")
                                #         exit()
                                chunks = [
                                    text_variables[i : i + 4]
                                    for i in range(0, len(text_variables), 4)
                                ]
                                if (
                                    len(chunks) > 0
                                    and len(chunks[-1]) < 4
                                    and chunks[-1] == b"\x00" * len(chunks[-1])
                                ):
                                    chunks = chunks[0:-1]
                                if len(chunks) > 0:
                                    text += (
                                        "{"
                                        + " ".join(
                                            [f"{b:02X}" for b in b"".join(chunks)]
                                        )
                                        + "}"
                                    )
                            else:
                                # Read padding
                                if params_io.tell() % 4 != 0:
                                    padding_size = (
                                        (params_io.tell() // 4) + 1
                                    ) * 4 - params_io.tell()
                                    padding = params_io.read(padding_size)
                                    if padding != b"\x00" * len(padding):
                                        print("Error. Expecting padding")
                                        exit()

                            param.value = text
                            # break
                        elif param.type == InstType.T:
                            param.value = unpack(f"I", params_io.read(4))[0]
                            value_type_str = "V_" + param.type_str.split("T_")[1]

                            for j in range(len(inst.params)):
                                # typedef enum pac_pointer_types {
                                #     FLOAT=16,
                                #     INTEGER=2,
                                #     ADDRESS=1,
                                #     POINTER_0x20=32,
                                #     POINTER_0x4=4,
                                #     POINTER_0x40=64,
                                #     POINTER_0x8=8,
                                #     UNKNOWN=0
                                # }
                                if inst.params[j].type_str == value_type_str:
                                    if param.value == 0x10:  # float
                                        inst.params[j].type |= InstType.FLOAT
                                    elif (
                                        param.value == 0x2
                                    ):  # int, short, uint, ushort?
                                        inst.params[j].type |= InstType.INT
                                    elif (
                                        param.value == 0x20
                                    ):  # int, short, uint, ushort?
                                        inst.params[j].type |= InstType.UINT
                                    else:  # 0x4, 0x8, 0x40
                                        inst.params[j].type |= InstType.INT
                                        # TODO
                                        # print(
                                        #     f"{offset:08X} {inst.type_name} Unknown Type 0x{param.value:X}"
                                        # )
                                        # exit(1)
                                    break
                        elif InstType.CONTINOUS in param.type:
                            sub_param_type = InstType.UINT
                            sub_param_type_str = "UINT"
                            if InstType.UINT in param.type:
                                sub_param_type = InstType.UINT
                                sub_param_type_str = "UINT"
                            elif InstType.INT in param.type:
                                sub_param_type = InstType.INT
                                sub_param_type_str = "INT"
                            elif InstType.FLOAT in param.type:
                                sub_param_type = InstType.FLOAT
                                sub_param_type_str = "FLOAT"
                            inst.params.remove(param)
                            params_last_offset = get_last_offset(params_io)
                            num_params = (params_last_offset - params_io.tell()) // 4
                            for c in range(num_params):
                                sub_param = InstParam()
                                sub_param.type = sub_param_type
                                sub_param.type_str = sub_param_type_str
                                sub_param.name = f"Continous {c+1}"
                                if sub_param_type == InstType.UINT:
                                    sub_param.value = unpack(f"I", params_io.read(4))[0]
                                elif sub_param_type == InstType.INT:
                                    sub_param.value = unpack(f"i", params_io.read(4))[0]
                                elif sub_param_type == InstType.FLOAT:
                                    sub_param.value = float(
                                        "{:.4f}".format(
                                            unpack(f"f", params_io.read(4))[0]
                                        )
                                    )
                                else:
                                    print(f"Error Continous unk {sub_param_type=}")
                                    exit()
                                inst.params.append(sub_param)
                            break
                        elif InstType.COUNT in param.type:
                            count = unpack(f"I", params_io.read(4))[0]
                            param.value = count
                            sub_param_type = InstType.UINT
                            sub_param_type_str = "UINT"
                            if InstType.UINT in param.type:
                                sub_param_type = InstType.UINT
                                sub_param_type_str = "UINT"
                            elif InstType.INT in param.type:
                                sub_param_type = InstType.INT
                                sub_param_type_str = "INT"
                            elif InstType.FLOAT in param.type:
                                sub_param_type = InstType.FLOAT
                                sub_param_type_str = "FLOAT"
                            # inst.params.remove(param)
                            for c in range(count):
                                sub_param = InstParam()
                                sub_param.type = sub_param_type
                                sub_param.type_str = sub_param_type_str
                                sub_param.name = f"Count {c+1}"
                                if sub_param_type == InstType.UINT:
                                    sub_param.value = unpack(f"I", params_io.read(4))[0]
                                elif sub_param_type == InstType.INT:
                                    sub_param.value = unpack(f"i", params_io.read(4))[0]
                                elif sub_param_type == InstType.FLOAT:
                                    sub_param.value = float(
                                        "{:.4f}".format(
                                            unpack(f"f", params_io.read(4))[0]
                                        )
                                    )
                                else:
                                    print(f"Error Count {sub_param_type=}")
                                    exit()
                                inst.params.append(sub_param)
                            # TODO Check if there are more parameters after the COUNT
                            break
                        elif InstType.UINT in param.type:
                            try:
                                param.value = unpack(f"I", params_io.read(4))[0]
                            except Exception as e:
                                print(e)
                                print(output)
                                print(inst)
                                exit()
                        elif InstType.INT in param.type:
                            param.value = unpack(f"i", params_io.read(4))[0]
                        elif InstType.FLOAT in param.type:
                            param.value = float(
                                "{:.4f}".format(unpack(f"f", params_io.read(4))[0])
                            )
                        elif param.type == InstType.ENTITY_ID:
                            param.value = unpack(f"I", params_io.read(4))[0]
                        elif param.type == InstType.EQUIP_ID:
                            param.value = unpack(f"I", params_io.read(4))[0]
                        elif param.type == InstType.KEYBIND_ID:
                            param.value = unpack(f"I", params_io.read(4))[0]
                        elif param.type == InstType.LOOT_ID:
                            param.value = unpack(f"I", params_io.read(4))[0]
                except struct.error as e:
                    print(f'Error "{inst.type_name}": {e}')
                    exit()
                # outfile.write(f"{inst.offset:08X}  {inst.type_name}  {inst.params}\n")
                instructions.append(inst)

                bytes_parsed = 0
                for param in inst.params:
                    if param.type == InstType.STR:
                        bytes_parsed = -1
                        break
                    else:
                        bytes_parsed += 4
                if bytes_parsed != -1:
                    if (
                        len(params_bytes) != bytes_parsed
                        and not "unk_" in inst.type_name
                    ):
                        # print (inst)
                        # print (len(params_bytes))
                        # print (bytes_parsed)
                        # exit()
                        # offset = inst.offset + 4 + bytes_parsed
                        # inst = Instruction(
                        #     type_id=inst_id,
                        #     type_subid=inst_subid,
                        #     type_name=f"RAW_BYTES_INST",
                        #     desc="Unk",
                        #     offset=offset,
                        #     params=[
                        #         InstParam(
                        #             name=None,
                        #             type=InstType.BYTES,
                        #             type_str="bytes",
                        #             value=params_bytes[bytes_parsed:],
                        #             # value=params_bytes,
                        #         )
                        #     ],
                        # )
                        # instructions.append(inst)
                        # infile.seek(infile.tell() - len(params_bytes) + bytes_parsed)
                        if len(instructions) > 0 and isinstance(
                            instructions[-1], Tuple
                        ):
                            instructions[-1][1].extend(params_bytes[bytes_parsed:])
                        else:
                            instructions.append(
                                (
                                    inst.offset + 4 + bytes_parsed,
                                    params_bytes[bytes_parsed:],
                                )
                            )
                # break

            # raw_bytes.extend(inst_type_bytes)
        # print_new_types(instructions)
        # exit()
        print(f'Generating "{output}"')
        with open(output, "w", encoding="utf-8") as outfile:
            for i, inst in enumerate(instructions):
                if isinstance(inst, Tuple):
                    offset = inst[0]
                    if i != 0:
                        try:
                            text = (
                                unpack(f"{len(inst[1])}s", bytearray(inst[1]))[0]
                                .decode("shift_jis")
                                .rstrip("\x00")
                            ).split("\x00")
                            outfile.write(f"{offset:08X}  STRING_LIST {text}\n")
                        except UnicodeDecodeError:
                            try:
                                chunks = [
                                    inst[1][i : i + 4]
                                    for i in range(0, len(inst[1]), 4)
                                ]
                                bytes_str = ""
                                for chunk_count, chunk in enumerate(chunks):
                                    if chunk_count != 0:
                                        bytes_str += ", "
                                    bytes_str += f"{unpack('I', chunk)[0]:X}"
                                outfile.write(f"{offset:08X}  RAW_BYTES {bytes_str}\n")
                            except Exception:
                                bytes_str = " ".join([f"{b:02X}" for b in inst[1]])
                                outfile.write(f"{offset:08X}  RAW_BYTES {bytes_str}\n")
                    else:
                        bytes_str = " ".join([f"{b:02X}" for b in inst[1]])
                        outfile.write(f"{offset:08X}  RAW_BYTES {bytes_str}\n")

                else:
                    outfile.write(
                        f"{inst.offset:08X}  {inst.type_name}({get_str_params(inst.params)})\n"
                        # f"{inst.offset:08X}  {inst.type_name}  {inst.params}\n"
                    )
                # if i == 2:
                #     # print(inst)
                #     exit()

        print_new_types(instructions)


if __name__ == "__main__":
    app()
