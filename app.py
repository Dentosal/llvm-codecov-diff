import re
from dataclasses import dataclass
from bs4 import BeautifulSoup
import argparse


parser = argparse.ArgumentParser(
    prog="llvm-codecov-diff",
    description="A html diff generator for llvm html coverage reports",
)
parser.add_argument("old")
parser.add_argument("new")
parser.add_argument("out", nargs="?")
args = parser.parse_args()

RE_FRAC = re.compile(r"\((?P<amount>\d+)/(?P<total>\d+)\)")


@dataclass
class OutOf:
    amount: int
    total: int

    @property
    def maxed(self):
        return self.amount == self.total


with open(args.old, "r") as f:
    old_html = BeautifulSoup(f.read(), features="html.parser")

with open(args.new, "r") as f:
    new_html = BeautifulSoup(f.read(), features="html.parser")

old_lines = old_html.find_all("tr")
new_lines = new_html.find_all("tr")

old_headers = [td.text.strip() for td in old_lines[0].find_all("td")]
new_headers = [td.text.strip() for td in new_lines[0].find_all("td")]
assert old_headers == new_headers, "Headers do not match"
headers = old_headers


def extract(line):
    cells = line.find_all("td")
    assert len(cells) == len(
        headers
    ), "Number of cells does not match number of headers"

    path = None
    line_data = {}
    for i, (header, column) in enumerate(zip(headers, cells)):
        if i == 0:
            if column.text != "Totals":
                path = column.find_all("a")[0].text
        elif m := RE_FRAC.search(column.text):
            line_data[header] = OutOf(
                amount=int(m.group("amount")), total=int(m.group("total"))
            )
        else:
            exit("missing column data")

    return path, line_data


per_file = {}
for ver, ver_lines in {"old": old_lines, "new": new_lines}.items():
    for line in ver_lines[1:]:
        path, fields = extract(line)
        if path not in per_file:
            per_file[path] = {}
        per_file[path][ver] = fields

files = [k for k in per_file.keys() if k is not None]
files.sort()


@dataclass
class ResultCell:
    old: OutOf
    new: OutOf

    def __str__(self):
        old = self.old
        new = self.new

        if old == new:
            return f"{old.amount}/{old.total} (No change)"
        elif old.total == new.total:
            return f"{{{old.amount} -> {new.amount}}}/{new.total}"
        elif old.amount == new.amount:
            return f"{old.amount}/{{{old.total} -> {new.total}}}"
        else:
            return f"{old.amount}/{old.total} -> {new.amount}/{new.total}"

    @property
    def style(self) -> str:
        if self.old == self.new:
            return "color: #ccc;"
        elif self.old.maxed and self.new.maxed:
            return "color: #999;"
        else:
            return "color: black;"


result = []
for file in files + [None]:
    result.append([file or "Totals"])
    for header in headers[1:]:
        has_old = "old" in per_file[file]
        has_new = "new" in per_file[file]
        assert has_old or has_new, "Malformed data"

        if not has_old:
            pass
        elif not has_new:
            pass
        else:
            old = per_file[file]["old"][header]
            new = per_file[file]["new"][header]
            result[-1].append(ResultCell(old=old, new=new))

html = """
<html><head>
<style>
table {
    border: 1px solid black;
    border-collapse: collapse;
    width: 100%;
    font-size: 1.2em;
}
td {
    border: 1px solid black;
    padding: 5px;
}
</style>
</head><body>
"""
html += "<table><thead>"
for header in headers:
    html += f"<th>{header}</th>"
html += "</thead><tbody>"
for row in result:
    if row[0] != result[-1][0] and all(item.old == item.new for item in row[1:]):
        continue
    for cell in row:
        style = getattr(cell, "style", "font-weight: bold; font: monospace;")
        html += f'<td style="{style}">{cell}</td>'
    html += "</tr>"
html += "</tbody></table></body></html>"

if args.out is None:
    print(html)
else:
    with open(args.out, "w") as f:
        f.write(html)
