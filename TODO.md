# todo.md

# handling failure

```bash
╭─ ❌ CRITICAL FAILURE | tinybot | coding_agents : Install Crush CLI ─╮
│ Execution Duration: 0.72s                                           │
│ Error Message: non-zero return code                                 │
│                                                                     │
│                                                                     │
╰─────────────────────────────────────────────────────────────────────╯
```

So with any of these, there needs to be some sort of an alert with the actual stack trace and ideally interpreted. So that's where we can maybe use the modules for.


Yeah, I mean given that this ran a few times without an issue here and then today it does, it makes me think that it's not checking for whether or not it's installed correctly. It's probably already installed.


---

##
