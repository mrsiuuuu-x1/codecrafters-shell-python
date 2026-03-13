import sys
import shutil
import os
import subprocess
import tty
import termios

BUILTIN = {"exit", "echo", "type", "pwd", "cd"}

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
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    return open(path, "a" if append else "w")


def get_completions(text):
    """Return sorted list of completions for the given prefix."""
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
    """Read a line from stdin with tab-completion support."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    buf = ""
    last_was_tab = False

    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)

            if ch in ("\r", "\n"):
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                last_was_tab = False
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
                last_was_tab = False
                return ""

            elif ch == "\x04":
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                raise EOFError

            elif ch == "\t":
                if " " not in buf:
                    completions = get_completions(buf)

                    if len(completions) == 1:
                        # Unique match
                        completed = completions[0]
                        suffix = completed[len(buf):]
                        buf = completed + " "
                        sys.stdout.write(suffix + " ")
                        sys.stdout.flush()
                        last_was_tab = False

                    elif len(completions) > 1:
                        prefix = os.path.commonprefix(completions)

                        if len(prefix) > len(buf):
                            # Can extend to common prefix
                            suffix = prefix[len(buf):]
                            buf = prefix
                            sys.stdout.write(suffix)
                            sys.stdout.flush()
                            last_was_tab = False
                        else:
                            if last_was_tab:
                                # Second tab — show all options
                                sys.stdout.write("\r\n")
                                sys.stdout.write("  ".join(completions))
                                sys.stdout.write("\r\n$ " + buf)
                                sys.stdout.flush()
                                last_was_tab = False
                            else:
                                # First tab — ring bell
                                sys.stdout.write("\a")
                                sys.stdout.flush()
                                last_was_tab = True
                    else:
                        # No completions
                        sys.stdout.write("\a")
                        sys.stdout.flush()
                        last_was_tab = False
                else:
                    last_was_tab = False

            elif ch >= " ":  # printable character
                last_was_tab = False
                buf += ch
                sys.stdout.write(ch)
                sys.stdout.flush()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

def run_pipeline(pipeline_parts):
    """Run a list of command strings connected by pipes."""
    procs = []
    prev_stdout = None

    for i, part in enumerate(pipeline_parts):
        tokens = parse_command(part.strip())
        if not tokens:
            continue
        is_last = (i == len(pipeline_parts) - 1)
        stdin_src = prev_stdout
        stdout_dst = None if is_last else subprocess.PIPE

        exe = shutil.which(tokens[0])
        if exe:
            p = subprocess.Popen(
                tokens,
                stdin=stdin_src,
                stdout=stdout_dst,
            )
            if prev_stdout:
                prev_stdout.close()
            prev_stdout = p.stdout
            procs.append(p)
        else:
            print(f"{tokens[0]}: command not found", file=sys.stderr)

    for p in procs:
        p.wait()

def run_command(cmd, args, stdout_target, stderr_target):
    def write_stdout(text):
        if stdout_target:
            stdout_target.write(text + "\n")
        else:
            print(text)

    def write_stderr(text):
        if stderr_target:
            stderr_target.write(text + "\n")
        else:
            print(text, file=sys.stderr)

    if cmd == "exit":
        code = int(args[0]) if args else 0
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

    else:
        exe = shutil.which(cmd)
        if exe:
            subprocess.run(
                [cmd] + args,
                stdout=stdout_target if stdout_target else None,
                stderr=stderr_target if stderr_target else None,
            )
        else:
            write_stderr(f"{cmd}: command not found")

def main():
    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        try:
            command = read_line_with_completion()
        except EOFError:
            break

        command = command.strip()
        if not command:
            continue

        # Handle pipelines
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


if __name__ == "__main__":
    main()