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
            # backslash outside quotes: escape next char literally
            i += 1
            current += command[i]
        elif c == "'":
            # single quotes: everything literal, no escaping
            i += 1
            while i < len(command) and command[i] != "'":
                current += command[i]
                i += 1
        elif c == '"':
            # double quotes: mostly literal, but backslash still escapes
            i += 1
            while i < len(command) and command[i] != '"':
                if command[i] == "\\" and i + 1 < len(command) and command[i+1] in ('"', '\\', '$', '\n'):
                    i += 1
                    current += command[i]
                else:
                    current += command[i]
                i += 1
        elif c == " ":
            if current:
                tokens.append(current)
                current = ""
        else:
            current += c
        i += 1
    if current:
        tokens.append(current)
    return tokens

def main():
    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()
        command = input().strip()
        if not command:
            continue

        parts = parse_command(command)
        cmd = parts[0]
        args = parts[1:]

        # Parse redirections out of args
        stdout_file = None
        stderr_file = None
        stdout_append = False
        stderr_append = False
        clean_args = []
        i = 0
        while i < len(args):
            if args[i] in (">>",):
                stdout_file = args[i+1]
                stdout_append = True
                i += 2
            elif args[i] == ">":
                stdout_file = args[i+1]
                stdout_append = False
                i += 2
            elif args[i] == "2>>":
                stderr_file = args[i+1]
                stderr_append = True
                i += 2
            elif args[i] == "2>":
                stderr_file = args[i+1]
                stderr_append = False
                i += 2
            else:
                clean_args.append(args[i])
                i += 1
        args = clean_args

        def open_out(path, append):
            return open(path, "a" if append else "w")

        stdout_target = open_out(stdout_file, stdout_append) if stdout_file else None
        stderr_target = open_out(stderr_file, stderr_append) if stderr_file else None

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
            break
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
            if shutil.which(cmd):
                subprocess.run(
                    [cmd] + args,
                    stdout=stdout_target if stdout_target else None,
                    stderr=stderr_target if stderr_target else None
                )
            else:
                write_stderr(f"{cmd}: command not found")

        if stdout_target:
            stdout_target.close()
        if stderr_target:
            stderr_target.close()

if __name__ == "__main__":
    main()