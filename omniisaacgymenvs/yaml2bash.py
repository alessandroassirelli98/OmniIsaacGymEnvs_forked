import argparse
import yaml

def parse_yaml_file(yaml_file):
    """Parse YAML file and return configurations."""
    with open(yaml_file, 'r') as file:
        return yaml.safe_load(file)

def create_bash_script(script, configurations):
    """Create a Bash script containing the call to Python with parsed parameters."""
    script_content = "#!/bin/bash\n\n"
    for idx, run in enumerate(configurations, start=1):
        run_name, params = list(run.items())[0]
        script_content += f"echo 'Running {run_name}'\n"
        arguments = " ".join([f"+{key}={value}" for key, value in params.items()])
        script_content += f"python {script} {arguments}\n"
    return script_content

if __name__ == "__main__":
    configurations = parse_yaml_file("launch_config.yaml")['configurations']
    script_content = create_bash_script("scripts/skrl/diana_tekken_PPOFD.py", configurations)

    with open("run_script.sh", "w") as f:
        f.write(script_content)

    print("Bash script 'run_script.sh' generated successfully!")
