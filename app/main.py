import sys
import shutil
import os
import subprocess
import tty
import termios
import re

BUILTIN = {"exit", "echo", "type", "pwd", "cd", "history"}
HISTORY_FILE = os.path.expanduser("~/.shell_history")
MAX_HISTORY = 1000
history = []

ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')


def strip_ansi(s):
    return ANSI_ESCAPE.sub('', s)


def load_history():
    global history
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            lines = [line.rstrip("\n") for line in f.readlines()]
            history = [l for l in lines if l]


def append_history_to_file(entries):
    d = os.path.dirname(HISTORY_FILE)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(HISTORY_FILE, "a") as f:
        for entry in entries:
            f.write(entry + "\n")


def write_history_to_file():
    d = os.path.dirname(HISTORY_FILE)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        for entry in history[-MAX_HISTORY:]:
            f.write(entry + "\n")


def add_history(line):
    line = strip_ansi(line).strip()
    if line:
        history.append(line)


def parse_command(command):
    tokens = []
    current = ""
    i = 0
    while i < len(command):
        c = command[i]
        if c == "\\" and i + 1 < len(command):
            i += 1
            current += command[i]
        elif c == "'":
            i += 1
            while i < len(command) and command[i] != "'":
                current += command[i]
                i += 1
        elif c == '"':
            i += 1
            while i < len(command) and command[i] != '"':
                if command[i] == "\\" and i + 1 < len(command) and command[i + 1] in ('"', '\\', '$', '\n'):
                    i += 1
                    current += command[i]
                else:
                    current += command[i]
                i += 1
        elif c in (" ", "\t"):
            if current:
                tokens.append(current)
                current = ""
        else:
            current += c
        i += 1
    if current:
        tokens.append(current)
    return tokens


def parse_redirections(args):
    stdout_file = None
    stderr_file = None
    stdout_append = False
    stderr_append = False
    clean_args = []
    i = 0
    while i < len(args):
        tok = args[i]
        if tok in (">>", "1>>"):
            stdout_file = args[i + 1]; stdout_append = True; i += 2
        elif tok in (">", "1>"):
            stdout_file = args[i + 1]; stdout_append = False; i += 2
        elif tok == "2>>":
            stderr_file = args[i + 1]; stderr_append = True; i += 2
        elif tok == "2>":
            stderr_file = args[i + 1]; stderr_append = False; i += 2
        else:
            clean_args.append(tok); i += 1
    return clean_args, stdout_file, stdout_append, stderr_file, stderr_append


def open_redirect(path, append):
    path = os.path.expanduser(path)
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    return open(path, "a" if append else "w")


def get_completions(text):
    completions = set()
    for b in BUILTIN:
        if b.startswith(text):
            completions.add(b)
    for directory in os.environ.get("PATH", "").split(":"):
        try:
            for name in os.listdir(directory):
                if name.startswith(text):
                    full = os.path.join(directory, name)
                    if os.access(full, os.X_OK):
                        completions.add(name)
        except (FileNotFoundError, PermissionError):
            pass
    return sorted(completions)


def read_line_with_completion():
    if not sys.stdin.isatty():
        sys.stdout.flush()
        try:
            return input()
        except EOFError:
            raise

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    buf = ""
    last_was_tab = False
    hist_index = len(history)
    saved_buf = ""

    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)

            if ch in ("\r", "\n"):
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                return buf

            elif ch == "\x7f":
                last_was_tab = False
                if buf:
                    buf = buf[:-1]
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()

            elif ch == "\x03":
                sys.stdout.write("^C\r\n")
                sys.stdout.flush()
                return ""

            elif ch == "\x04":
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                raise EOFError

            elif ch == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[A":
                    if hist_index == len(history):
                        saved_buf = buf
                    if hist_index > 0:
                        hist_index -= 1
                        new_buf = history[hist_index]
                        sys.stdout.write("\r$ " + new_buf + " " * max(0, len(buf) - len(new_buf)) + "\r$ " + new_buf)
                        sys.stdout.flush()
                        buf = new_buf
                elif seq == "[B":
                    if hist_index < len(history):
                        hist_index += 1
                        new_buf = history[hist_index] if hist_index < len(history) else saved_buf
                        sys.stdout.write("\r$ " + new_buf + " " * max(0, len(buf) - len(new_buf)) + "\r$ " + new_buf)
                        sys.stdout.flush()
                        buf = new_buf
                last_was_tab = False

            elif ch == "\t":
                if " " not in buf:
                    completions = get_completions(buf)
                    if len(completions) == 1:
                        completed = completions[0]
                        suffix = completed[len(buf):]
                        buf = completed + " "
                        sys.stdout.write(suffix + " ")
                        sys.stdout.flush()
                        last_was_tab = False
                    elif len(completions) > 1:
                        prefix = os.path.commonprefix(completions)
                        if len(prefix) > len(buf):
                            suffix = prefix[len(buf):]
                            buf = prefix
                            sys.stdout.write(suffix)
                            sys.stdout.flush()
                            last_was_tab = False
                        else:
                            if last_was_tab:
                                sys.stdout.write("\r\n" + "  ".join(completions) + "\r\n$ " + buf)
                                sys.stdout.flush()
                                last_was_tab = False
                            else:
                                sys.stdout.write("\a")
                                sys.stdout.flush()
                                last_was_tab = True
                    else:
                        sys.stdout.write("\a")
                        sys.stdout.flush()
                        last_was_tab = False
                else:
                    last_was_tab = False

            elif ch >= " ":
                last_was_tab = False
                buf += ch
                sys.stdout.write(ch)
                sys.stdout.flush()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def format_history(entries, start_index):
    lines = []
    for i, entry in enumerate(entries):
        num = start_index + i + 1
        lines.append(f"  {num}  {entry}")
    return lines


def run_builtin_to_string(cmd, args):
    out = []
    if cmd == "echo":
        out.append(" ".join(args))
    elif cmd == "pwd":
        out.append(os.getcwd())
    elif cmd == "type":
        target = args[0] if args else ""
        if target in BUILTIN:
            out.append(f"{target} is a shell builtin")
        else:
            found = shutil.which(target)
            if found:
                out.append(f"{target} is {found}")
            else:
                out.append(f"{target}: not found")
    elif cmd == "history":
        n = None
        if args:
            try:
                n = int(args[0])
            except ValueError:
                pass
        entries = history[-n:] if n else history
        start = len(history) - len(entries)
        out.extend(format_history(entries, start))
    return "\n".join(out)


def run_pipeline(pipeline_parts):
    parsed_parts = []
    for part in pipeline_parts:
        tokens = parse_command(part.strip())
        if tokens:
            parsed_parts.append(tokens)

    if not parsed_parts:
        return

    procs = []
    prev_read = None

    for i, tokens in enumerate(parsed_parts):
        cmd = tokens[0]
        args = tokens[1:]
        is_last = (i == len(parsed_parts) - 1)
        is_builtin = cmd in BUILTIN

        if is_builtin:
            builtin_out = run_builtin_to_string(cmd, args)
            if is_last:
                if prev_read:
                    prev_read.close()
                sys.stdout.write(builtin_out + "\n")
                sys.stdout.flush()
            else:
                r_fd, w_fd = os.pipe()
                with os.fdopen(w_fd, "w") as wf:
                    wf.write(builtin_out + "\n")
                if prev_read:
                    prev_read.close()
                prev_read = os.fdopen(r_fd, "r")
        else:
            exe = shutil.which(cmd)
            if not exe:
                sys.stderr.write(f"{cmd}: command not found\n")
                sys.stderr.flush()
                if prev_read:
                    prev_read.close()
                return

            stdin_src = prev_read if prev_read else None
            stdout_dst = None if is_last else subprocess.PIPE

            p = subprocess.Popen(tokens, stdin=stdin_src, stdout=stdout_dst)
            if prev_read:
                prev_read.close()
            prev_read = p.stdout
            procs.append(p)

    for p in procs:
        p.wait()


def run_command(cmd, args, stdout_target, stderr_target):
    def write_stdout(text):
        if stdout_target:
            stdout_target.write(text + "\n")
            stdout_target.flush()
        else:
            sys.stdout.write(text + "\n")
            sys.stdout.flush()

    def write_stderr(text):
        if stderr_target:
            stderr_target.write(text + "\n")
            stderr_target.flush()
        else:
            sys.stderr.write(text + "\n")
            sys.stderr.flush()

    if cmd == "exit":
        code = int(args[0]) if args else 0
        write_history_to_file()
        sys.exit(code)

    elif cmd == "echo":
        write_stdout(" ".join(args))

    elif cmd == "pwd":
        write_stdout(os.getcwd())

    elif cmd == "cd":
        path = os.path.expanduser(args[0] if args else "~")
        try:
            os.chdir(path)
        except FileNotFoundError:
            write_stderr(f"cd: {path}: No such file or directory")

    elif cmd == "type":
        target = args[0] if args else ""
        if target in BUILTIN:
            write_stdout(f"{target} is a shell builtin")
        else:
            found_path = shutil.which(target)
            if found_path:
                write_stdout(f"{target} is {found_path}")
            else:
                write_stderr(f"{target}: not found")

    elif cmd == "history":
        n = None
        if args:
            try:
                n = int(args[0])
            except ValueError:
                pass
        entries = history[-n:] if n else history
        start = len(history) - len(entries)
        for line in format_history(entries, start):
            write_stdout(line)

    else:
        exe = shutil.which(cmd)
        if exe:
            subprocess.run(
                [cmd] + args,
                stdout=stdout_target if stdout_target else None,
                stderr=stderr_target if stderr_target else None,
            )
            if stdout_target:
                stdout_target.flush()
        else:
            write_stderr(f"{cmd}: command not found")


def main():
    load_history()
    session_start = len(history)

    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        try:
            command = read_line_with_completion()
        except EOFError:
            append_history_to_file(history[session_start:])
            break

        command = strip_ansi(command).strip()
        if not command:
            continue

        add_history(command)

        if "|" in command:
            pipeline_parts = command.split("|")
            run_pipeline(pipeline_parts)
            continue

        parts = parse_command(command)
        if not parts:
            continue

        cmd = parts[0]
        args = parts[1:]

        args, stdout_file, stdout_append, stderr_file, stderr_append = parse_redirections(args)

        stdout_target = open_redirect(stdout_file, stdout_append) if stdout_file else None
        stderr_target = open_redirect(stderr_file, stderr_append) if stderr_file else None

        try:
            run_command(cmd, args, stdout_target, stderr_target)
        finally:
            if stdout_target:
                stdout_target.close()
            if stderr_target:
                stderr_target.close()

    write_history_to_file()


if __name__ == "__main__":
    main()