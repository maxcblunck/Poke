todos = []

def add_todo(task):
    todos.append({"task": task, "done": False})
    print(f"Added: {task}")

def complete_todo(index):
    if 0 <= index < len(todos):
        todos[index]["done"] = True
        print(f"Completed: {todos[index]['task']}")
    else:
        print("Invalid index.")

def show_todos():
    if not todos:
        print("No tasks yet.")
        return
    for i, todo in enumerate(todos):
        status = "[x]" if todo["done"] else "[ ]"
        print(f"{i}. {status} {todo['task']}")

def run():
    print("To-Do List — commands: add, done, list, quit")
    while True:
        cmd = input("> ").strip().lower()
        if cmd == "quit":
            break
        elif cmd == "list":
            show_todos()
        elif cmd.startswith("add "):
            add_todo(cmd[4:])
        elif cmd.startswith("done "):
            try:
                complete_todo(int(cmd[5:]))
            except ValueError:
                print("Usage: done <number>")
        else:
            print("Unknown command.")

if __name__ == "__main__":
    run()
