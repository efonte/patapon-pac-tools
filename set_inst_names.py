import collections

from rich import print

functions = {}
# with open("[P3] - PAC Instruction Dump.txt", "r", encoding="utf-8") as infile:
with open("[P2] - PAC Instruction Dump.txt", "r", encoding="utf-8") as infile:
    for line in infile.readlines():
        category, id, offset, func_name = line.rstrip("\n").split(", ")
        # category = int(category[2:], 16)
        category = category[2:].upper()
        id = int(id[2:], 16)
        # print(f"{category:02X} {id:04X} {func_name}")
        functions[f"{category}_{id:04X}"] = (category, id, func_name)

func_names = []
for key, value in functions.items():
    func_names.append(value[2])
duplicated_func_names = [
    item for item, count in collections.Counter(func_names).items() if count > 1
]

# outfile = open("p3_instruction_set_new.csv", "w", encoding="utf-8")
# with open("p3_instruction_set.csv", "r", encoding="utf-8") as infile:
outfile = open("p2_instruction_set_new.csv", "w", encoding="utf-8")
with open("p2_instruction_set.csv", "r", encoding="utf-8") as infile:
    for line in infile.readlines():
        category, id, func_name, desc, params = line.rstrip("\n").split(";")
        try:
            _, _, func_name_new = functions[f"{category}_{id}"]
        except KeyError:
            func_name_new = func_name
        if func_name_new in duplicated_func_names:
            func_name_new = f"{func_name_new}{category}"
        outfile.write(f"{category};{id};{func_name_new};{desc};{params}\n")
