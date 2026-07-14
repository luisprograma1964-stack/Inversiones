import os

directory = r"C:\Para mi\Inversiones"
files = ["captura_noticias.py", "homologador_datos.py", "supervisor_del_sistema.py", "app.py"]

for filename in files:
    filepath = os.path.join(directory, filename)
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    new_lines = []
    has_global = False
    
    for i, line in enumerate(lines):
        if line.strip() == "import notificador_telegram":
            if i > 100:  # local import inside a function
                new_lines.append(line.replace("import notificador_telegram", "pass # import notificador_telegram"))
            else:
                has_global = True
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    if not has_global:
        new_lines.insert(5, "import notificador_telegram\n")
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    print(f"Fixed {filename}")
