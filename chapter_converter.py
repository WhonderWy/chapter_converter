from subprocess import run
import argparse
import datetime
import re
from os.path import exists, splitext
from os import remove
import win32clipboard

import chardet


def get_clipboard_data():
    win32clipboard.OpenClipboard()
    data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    return data


def set_clipboard_data(data):
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(data, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()


def ms_to_timestamp(ms):
    ms = int(ms)
    return str(datetime.timedelta(seconds=ms // 1000)) + "." + str(ms % 1000).zfill(3)


def timestamp_to_ms(timestamp):
    timestamp_split = re.split("[:.]", timestamp)
    if len(timestamp_split) == 4:
        h, m, s, ms = timestamp_split
    elif len(timestamp_split) == 3:
        h, m, s = timestamp_split
        ms = 0
    elif len(timestamp_split) == 2:
        m, s = timestamp_split
        h = 0
        ms = 0
    else:
        h = 0
        m = 0
        s = 0
        ms = 0

    return str(1000 * (int(h) * 3600 + int(m) * 60 + int(s)) + int(ms))

def format_time(time):
    timestamp_split = re.split("[:.]", time)
    if len(timestamp_split) == 4:
        h, m, s, ms = timestamp_split
    elif len(timestamp_split) == 3:
        h, m, s = timestamp_split
        ms = "00"
    elif len(timestamp_split) == 2:
        m, s = timestamp_split
        h = "00"
        ms = "00"
    else:
        h = "00"
        m = "00"
        s = "00"
        ms = "000"

    return f"{str(h):2}:{str(m):2}:{str(s):2}.{str(ms):3}"


def load_file_content(filename):
    # Detect file encoding
    with open(filename, "rb") as file:
        raw = file.read()
        encoding = chardet.detect(raw)["encoding"]

    # Detect format of input file
    with open(filename, encoding=encoding) as f:
        return f.readlines()


def main(*paras):

    parser = argparse.ArgumentParser()
    parser.add_argument("filename", nargs="?", help="input filename")
    parser.add_argument(
        "-f",
        "--format",
        choices=["simple", "pot", "ogm", "tab", "xml"],
        help="output format (default: pot)",
    )
    parser.add_argument(
        "--mp4-charset",
        help="input chapter charset for mp4 file, since it can't be auto detected (default: utf-8)",
        default="utf-8",
    )
    parser.add_argument(
        "--charset",
        help="output file charset (default: utf-8-sig)",
        default="utf-8-sig",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="output filename (default: original_filename.format[.txt])",
    )
    parser.add_argument(
        "-c",
        "--clipboard",
        action="store_true",
        help="automatically process text in clipboard and save it back.",
    )
    if paras:
        paras = list(map(str, paras))
        args = parser.parse_args(paras)
    else:
        args = parser.parse_args()

    # Input handling
    if args.filename and exists(args.filename):
        if args.filename.lower().endswith(".xml"):
            run(["mkvmerge", "-o", "temp.mks", "--chapters", args.filename])
            run(["mkvextract", "temp.mks", "chapters", "-s", "temp.ogm.txt"])
            lines = load_file_content("temp.ogm.txt")
            remove("temp.mks")
            remove("temp.ogm.txt")
        elif args.filename.lower().split(".")[-1] in ["mp4", "mkv"]:
            run(
                [
                    "mkvmerge",
                    "-o",
                    "temp.mks",
                    "-A",
                    "-D",
                    "--chapter-charset",
                    args.mp4_charset,
                    args.filename,
                ]
            )
            run(["mkvextract", "temp.mks", "chapters", "-s", "temp.ogm.txt"])
            lines = load_file_content("temp.ogm.txt")
            remove("temp.mks")
            remove("temp.ogm.txt")
        else:
            lines = load_file_content(args.filename)
    elif args.clipboard:
        f = get_clipboard_data()
        if f:
            print("Get data from clipboard:")
            print(f)
            lines = f.splitlines()
        else:
            print("No valid input data in clipboard!")
            return 0
    else:
        print("Input file missing or invalid!")
        return 0

    # Remove empty lines
    lines = list(filter(lambda x: not re.match(r"^\s*$", x), lines))
    input_format = ""
    YOUTUBE_RE = r"([0-9:.]+?) ((\d* )?(.+))"
    SIMPLE_RE = r"([0-9:.]+?), *(.+)"
    TAB_RE = r"([0-9:.].+?)\t(.+)"
    MEDIAINFO_RE = r"([0-9:.]+?)\s+:\s[a-z]{0,2}:(.+)"
    if re.match(YOUTUBE_RE, lines[0]):
        input_format = "youtube"
    elif re.match(SIMPLE_RE, lines[0]):
        input_format = "simple"
    elif re.match(TAB_RE, lines[0]):
        input_format = "tab"
    elif re.match(r"CHAPTER\d", lines[0]):
        input_format = "ogm"
    elif lines[0].startswith("[Bookmark]"):
        input_format = "pot"
    elif lines[0].startswith("Menu"):
        if re.match(MEDIAINFO_RE, lines[1]):
            lines = lines[1:]
            input_format = "mediainfo"
    elif re.match(MEDIAINFO_RE, lines[0]):
        input_format = "mediainfo"
    if not input_format:
        print("Can't guess file format!")
        return 0

    # Input text parsing
    chapters = []
    if input_format == "youtube":
        for line in lines:
            m = re.match(YOUTUBE_RE, line)
            if m:
                chapters.append((m.group(1), m.group(2)))
    elif input_format == "simple":
        for line in lines:
            m = re.match(SIMPLE_RE, line)
            if m:
                chapters.append((m.group(1), m.group(2)))
    elif input_format == "tab":
        for line in lines:
            m = re.match(TAB_RE, line)
            if m:
                chapters.append((m.group(1), m.group(2)))
    elif input_format == "ogm":
        for i in range(0, len(lines), 2):
            line1 = lines[i].strip()  # Remove \n at the end
            line2 = lines[i + 1].strip()
            chapters.append(
                (line1[line1.index("=") + 1 :], line2[line2.index("=") + 1 :])
            )
    elif input_format == "pot":
        for line in lines[1:]:
            m = re.match(r"\d+=(\d+)\*([^*]+)", line.strip())
            if m:
                timestamp = ms_to_timestamp(m.group(1))
                chapters.append((timestamp, m.group(2)))
    elif input_format == "mediainfo":
        for line in lines:
            m = re.match(MEDIAINFO_RE, line)
            if m:
                chapters.append((m.group(1), m.group(2)))

    # Set default output format if not specified.
    if not args.format:
        args.format = "pot"  # Default to pot
        if args.clipboard and input_format != "tab":
            args.format = (
                "tab"  # Default to "tab" if get from clipboard for spreadsheet editing.
            )
        if args.output:  # Get output format from output filename, if speicified.
            ext = splitext(args.output)[-1]
            if ext.lower() == ".pbf":
                args.format = "pot"
            elif ext.lower() == ".xml":
                args.format = "xml"
            elif ext.lower() == ".txt":
                args.format = "ogm"

    # Output filename handling
    if args.clipboard and not args.output:
        pass
    else:
        if args.output:
            new_filename = args.output
            args.clipboard = False
        else:
            if args.format == "pot":
                new_filename = f"{splitext(args.filename)[0]}.pbf"
            elif args.format == "xml":
                new_filename = f"{splitext(args.filename)[0]}.xml"
            else:
                new_filename = f"{splitext(args.filename)[0]}.{args.format}.txt"
        # Ensure to not override existing file(s)
        i = 2
        stem = splitext(new_filename)[0]
        ext = splitext(new_filename)[1]
        while exists(new_filename):
            new_filename = f"{stem} ({i}){ext}"
            i += 1

    # Genreate output text
    output = ""
    if args.format == "tab":
        for time, title in chapters:
            output = output + f"{time}\t{title}\n"
    elif args.format == "simple":
        for time, title in chapters:
            output = output + f"{time},{title}\n"
    elif args.format in ["ogm", "xml"]:
        i = 1
        for time, title in chapters:
            output = output + f"CHAPTER{i:02}={format_time(time)}\n"
            output = output + f"CHAPTER{i:02}NAME={title}\n"
            i += 1
    elif args.format == "pot":
        i = 0
        output = output + "[Bookmark]\n"
        for time, title in chapters:
            output = output + f"{i}={timestamp_to_ms(time)}*{title}*\n"
            i += 1

    # Output to clipboard/file
    if args.clipboard:
        print("Set data to clipboard:")
        print(output)
        set_clipboard_data(output.replace("\n", "\r\n"))
    elif args.format == "xml":
        with open("temp.ogm.txt", "w", encoding=args.charset) as f:
            f.write(output)
        run(["mkvmerge", "-o", "temp.mks", "--chapters", "temp.ogm.txt"])
        run(["mkvextract", "temp.mks", "chapters", new_filename])
        remove("temp.mks")
        remove("temp.ogm.txt")
    else:
        with open(new_filename, "w", encoding=args.charset) as f:
            f.write(output)


if __name__ == "__main__":
    main()
