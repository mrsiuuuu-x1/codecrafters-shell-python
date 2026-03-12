import sys
import shutil
import os
import subprocess

BUILTIN = {"exit", "echo", "type", "pwd", "cd"}


def parse_command(command):
    tokens = []
    current = ""
    i = 0
    while i < len(command):
        c = command[i]

        if c == "\\" and i + 1 < len(command):
            # backslash outside quotes: next char is literal
            i += 1
            current += command[i]

        elif c == "'":
            # single quotes: everything inside is literal, no escaping at all
            i += 1
            while i < len(command) and command[i] != "'":
                current += command[i]
                i += 1
            # skip closing '

        elif c == '"':
            # double quotes: mostly literal, but \\ \" \$ \newline are still escape sequences
            i += 1
            while i < len(command) and command[i] != '"':
                if command[i] == "\\" and i + 1 < len(command) and command[i + 1] in ('"', '\\', '$', '\n'):
                    i += 1
                    current += command[i]
                else:
                    current += command[i]
                i += 1
            # skip closing "

        elif c == " " or c == "\t":
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
    """
    Pull redirection tokens out of the args list.
    Returns (clean_args, stdout_file, stdout_append, stderr_file, stderr_append).
    Handles: >, 1>, >>, 1>>, 2>, 2>>
    """
    stdout_file = None
    stderr_file = None
    stdout_append = False
    stderr_append = False
    clean_args = []

    i = 0
    while i < len(args):
        tok = args[i]

        if tok in (">>", "1>>"):
            stdout_file = args[i + 1]
            stdout_append = True
            i += 2
        elif tok in (">", "1>"):
            stdout_file = args[i + 1]
            stdout_append = False
            i += 2
        elif tok == "2>>":
            stderr_file = args[i + 1]
            stderr_append = True
            i += 2
        elif tok == "2>":
            stderr_file = args[i + 1]
            stderr_append = False
            i += 2
        else:
            # Handle cases like "2>/tmp/foo" (no space between operator and path)
            # by re-tokenising inside parse_command we won't hit this, but just in case:
            clean_args.append(tok)
            i += 1

    return clean_args, stdout_file, stdout_append, stderr_file, stderr_append


def open_redirect(path, append):
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    return open(path, "a" if append else "w")


def main():
    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        try:
            command = input()
        except EOFError:
            break

        command = command.strip()
        if not command:
            continue

        parts = parse_command(command)
        if not parts:
            continue

        cmd = parts[0]
        args = parts[1:]

        # Extract any redirection operators
        args, stdout_file, stdout_append, stderr_file, stderr_append = parse_redirections(args)

        # Open redirection targets
        stdout_target = open_redirect(stdout_file, stdout_append) if stdout_file else None
        stderr_target = open_redirect(stderr_file, stderr_append) if stderr_file else None

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

        try:
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

        finally:
            if stdout_target:
                stdout_target.close()
            if stderr_target:
                stderr_target.close()


if __name__ == "__main__":
    main()