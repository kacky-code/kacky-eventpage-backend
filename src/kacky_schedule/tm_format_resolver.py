import re


class TMstr:
    def __init__(self, string):
        self.string = re.sub(r"\$[0-9a-fA-F]{3}|\$[wnoitsgzWNOITSGZ$]", "", string)

        # replace color codes with html
        htmlstr = string
        found = re.findall(r"\$[0-9a-fA-F]{3}", string)
        for f in found:
            # this is stupid, but we need to somehow escape the '$'
            htmlstr = re.sub(
                r"\$" + f"{f[1:]}", f"</span><span style='color:#{f[1:]}'>", htmlstr
            )
        # remove leading "</span>" and add a "</span>" at the end
        htmlstr = re.sub("</span>", "", htmlstr, count=1)

        # replace style formatters
        formatters = {
            "w": '<span style="letter-spacing: +0.1em;font-size:larger">',  # wide font
            "n": '<span style="letter-spacing: -0.1em;font-size:smaller">',  # narrow
            "o": '<span style="font-weight:bold">',  # bold font
            "i": '<span style="font-style:italic">',  # italic font
            "t": '<span style="text-transform:uppercase">',  # uppercase text
            "s": '<span style="text-shadow: 1px 1px 1px #000">',  # drop shadow
            "g": '<span style="color:#fff">',  # reset to default color
            "z": '<span style="font-style:italic">',  # reset default text style
            "$": "$",
        }  # display '$' char

        style_spans = 0
        # find all remaining single char formater strings in htmlstr
        formatmatches = re.findall(
            "|".join(
                [
                    r"\$" + f"{str.lower(f)}|" + r"\$" + f"{str.upper(f)}"
                    for f in formatters.keys()
                ]
            ),
            htmlstr,
        )
        for match in formatmatches:
            if match == "$z":
                resetstr = "</span>" * style_spans
                re.sub(match, resetstr, htmlstr, count=1)
            htmlstr = re.sub(
                r"\$" + f"{match[1:]}", formatters[match[1:]], htmlstr, count=1
            )
            style_spans += 1

        htmlstr += "</span>" * style_spans
        self.html = htmlstr


def printtest(string):
    print("=============================")
    tm = TMstr(string)
    print("Original")
    print(string)
    print("str only")
    print(tm.string)
    print("html")
    print(tm.html)
    print("=============================")


if __name__ == "__main__":
    teststr1 = "$f00$f3b\u05d3\u05d5\u05d6\u03c2 $ga$nmgrebor$wn L\u0192s"
    teststr2 = "$w$999c¢¬$c60Cork$0aascrew"
    teststr3 = "$CCC$idebil.$z$s$a00Cѳrk$0f1s$0a5crew"
    teststr4 = "$o$i$a00K$a60a$aa0ck$0a0iest Kack$a00$a00y $g7 - Server 4"

    printtest(teststr1)
    printtest(teststr2)
    printtest(teststr3)
    printtest(teststr4)
