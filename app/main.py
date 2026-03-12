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
        if c == "'":
            i += 1
            while i < len(command) and command[i] != "'":
                current += command[i]
                i += 1
        elif c == '"':
            i += 1
            while i < len(command) and command[i] != '"':
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

        if cmd == "exit":
            break
        elif cmd == "echo":
            print(" ".join(args))
        elif cmd == "pwd":
            print(os.getcwd())
        elif cmd == "cd":
            path = os.path.expanduser(args[0] if args else "~")
            try:
                os.chdir(path)
            except FileNotFoundError:
                print(f"cd: {path}: No such file or directory")
        elif cmd == "type":
            target = args[0] if args else ""
            if target in BUILTIN:
                print(f"{target} is a shell builtin")
            else:
                found_path = shutil.which(target)
                if found_path:
                    print(f"{target} is {found_path}")
                else:
                    print(f"{target}: not found")
        else:
            if shutil.which(cmd):
                subprocess.run(parts)
            else:
                print(f"{cmd}: command not found")

if __name__ == "__main__":
    main()