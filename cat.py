import os
from gitignore_parser import parse_gitignore

files_to_concatenate = [
    # Core application files
    'app/__init__.py',           # Flask app initialization
    #'run.py',                    # Application entry point
    'config.py',                 # Main configuration
    #'.flaskenv',                 # Flask environment variables
    
    # Routes and Views
    #'app/routes/__init__.py',    # Routes initialization
    'app/routes/main.py',        # Main route handlers
    #'app/routes/vendor.py',      # Vendor routes
    #'app/routes/agency.py',      # Agency routes
    #'app/routes/standard.py',    # Standards routes
    #'app/routes/integrations.py', # Integration routes
    #'app/routes/component.py',   # Component routes
    #'app/routes/function.py',    # Function routes
    'app/routes/configurations.py', # Configuration routes
    
    # Models and Data
    #'app/models/__init__.py',    # Models initialization
    'app/models/tran.py',        # Core data model
    #'app/models/gtfs.py',        # GTFS data models
    
    # Forms and Auth
    #'app/forms/__init__.py',     # Forms initialization
    #'app/forms/forms.py',        # Form definitions
    #'app/auth.py',               # Authentication logic
    
    # Agents
    'app/agents/__init__.py',    # Agents initialization
    'app/agents/agency_agent.py',# Agency business logic
    #'app/agents/component_agent.py', # Component business logic
    
    # Utils
    #'app/utils/__init__.py',     # Utils initialization
    #'app/utils/errors.py',       # Error handling
    #'app/utils/logging.py',      # Standard logging functions
    
    # Frontend Assets
    #'tailwind/input.css',        # Tailwind source CSS
    #'tailwind.config.js',        # Tailwind configuration
    #'postcss.config.js',         # PostCSS configuration
    #'app/static/css/style.css',  # Custom styles
    #'app/static/js/main.js',     # Main JavaScript file
    #'app/static/js/htmx.min.js',   # Vendor JavaScript file
    
    # Templates
    'app/templates/base.html',    # Base template
    'app/templates/index.html',   # Main page
    #'app/templates/systems.html', # Systems page
    #'app/templates/vendors.html', # Vendors page
    'app/templates/components.html', # Components page
    #'app/templates/standards.html',  # Standards page
    #'app/templates/integrations.html', # Integrations page
    #'app/templates/functional_areas.html', # Functional areas page
    #'app/templates/agencies.html',   # Agencies page
    #'app/templates/contribute.html', # Contribute page
    'app/templates/configurations.html', # Configurations page
    'app/templates/component_detail.html', # Component detail page
    
    # Template Fragments
    #'app/templates/fragments/vendor_details.html',
    #'app/templates/fragments/vendor_form.html',
    #'app/templates/fragments/vendor_list.html',
    #'app/templates/fragments/agency_details.html',
    #'app/templates/fragments/agency_list.html',
    #'app/templates/fragments/agency_form.html',
    #'app/templates/fragments/functional_area_details.html',
    #'app/templates/fragments/functional_area_form.html',
    #'app/templates/fragments/functional_area_list.html',
    
    # Scripts
    #'scripts/load_functional_areas.py',
    #'scripts/load_tran.py',
    #'scripts/load_transit_systems.py',
    #'scripts/load_vendors.py',
    #'scripts/load_standards.py',
    
    # Tests
    #'tests/__init__.py',
    #'tests/test_app.py',
    #'tests/test_phase1.py',
    #'tests/test_phase2.py',
    #'tests/test_phase2_functional_areas.py',
    
    # Documentation
    #'prompts/Technical_Design.md',
    #'prompts/Data_Model.md',
    #'prompts/Vendors.md',
    #'prompts/More_Vendors.md',
    #'prompts/Full_Vendors.md',
    'README.md',

    # Data
    #'data/ctran/agency.csv',
    #'data/ctran/components.csv',
    #'data/ctran/functional_areas.csv',
    #'data/ctran/function_implementations.csv',
    #'data/ctran/functions.csv',
    #'data/ctran/vendors.csv',
]

# Define the output file
output_file = 'combined.txt'

def create_directory_tree(startpath):
    """Generate a string representation of the directory tree, excluding .gitignore files, migrations/, and .git/."""
    tree = []
    
    # Parse .gitignore file
    gitignore_file = os.path.join(startpath, '.gitignore')
    if os.path.exists(gitignore_file):
        ignorer = parse_gitignore(gitignore_file)
    else:
        ignorer = lambda f: False  # If no .gitignore, don't ignore anything
    
    # Additional directories to exclude
    exclude_dirs = {'migrations', '.git', 'scripts', 'data', 'prompts'}
    
    for root, dirs, files in os.walk(startpath, topdown=True):
        # Remove ignored and explicitly excluded directories
        dirs[:] = [d for d in dirs if not ignorer(os.path.join(root, d)) and d not in exclude_dirs and not d.startswith('zzz')]
        
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * level
        tree.append(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            if not ignorer(os.path.join(root, f)) and not f.startswith('zzz'):
                tree.append(f"{subindent}{f}")
    return '\n'.join(tree)

def concatenate_files(file_list, output_file):
    tree = create_directory_tree('.')  # Adjust '.' to the root of your project if necessary
    with open(output_file, 'w') as outfile:
        outfile.write("# Project Directory Structure\n")
        outfile.write(tree + "\n\n# End of Directory Structure\n\n")
        for file_name in file_list:
            if os.path.exists(file_name):
                with open(file_name, 'r') as infile:
                    outfile.write(f'# Start of {file_name}\n')
                    outfile.write(infile.read())
                    outfile.write(f'\n# End of {file_name}\n\n')
            else:
                print(f"File {file_name} does not exist.")

if __name__ == '__main__':
    concatenate_files(files_to_concatenate, output_file)
    print(f"Files concatenated into {output_file}")
