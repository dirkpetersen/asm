#! /bin/bash

PMIN="8" # python3 minor version = 3.8)

asm_update() {
  curl -Ls https://raw.githubusercontent.com/dirkpetersen/asm/main/asm.py?token=$(date +%s) \
        -o ~/.local/bin/asm.py

  curl -Ls https://raw.githubusercontent.com/dirkpetersen/asm/main/asm?token=$(date +%s) \
        -o ~/.local/bin/asm

  chmod +x ~/.local/bin/asm


}
echo ""
umask 0002
if [[ $1 == "update" ]]; then
  echo -e "  Updating asm, please wait ...\n"
  asm_update
  asm --version
  echo -e "\n  asm updated! Run 'asm --help'\n"  
  exit
fi 
echo "Installing asm, please wait ..."
### checking for correct Python version 
P3=$(which python3)
if [[ -z ${P3} ]]; then
  echo "python3 could not be found, please install Python >= 3.${PMIN} first"
  exit
fi
python3 -m pip --disable-pip-version-check install --upgrade --user visidata
if [[ $(${P3} -c "import sys; print(sys.version_info >= (3,${PMIN}))") == "False" ]]; then
  echo "Python >= 3.${PMIN} required and your default ${P3} is too old."
  printf "Trying to load Python through the modules system ... "
  module load python > /dev/null 2>&1
  module load Python > /dev/null 2>&1
  echo "Done!"
  printf "Starting Python from default module ... "
  if [[ $(python3 -c "import sys; print(sys.version_info >= (3,${PMIN}))") == "False" ]]; then
    echo "Done!"
    printf "The default Python module is older than 3.${PMIN}. Trying Python/3.${PMIN} ... "
    module load python/3.${PMIN} > /dev/null 2>&1
    module load Python/3.${PMIN} > /dev/null 2>&1
    echo "Done!"
    printf "Starting Python 3.${PMIN} from module ... "
    if [[ $(python3 -c "import sys; print(sys.version_info >= (3,${PMIN}))") == "False" ]]; then
      echo "Failed to load Python 3.${PMIN}. Please load a Python module >= 3.${PMIN} manually."
      exit
    fi
    echo "Done!"
  else 
    echo "Done!"
  fi
fi
python3 -m pip --disable-pip-version-check install --upgrade --user visidata
### Fixing a potentially broken LD_LIBRARY_PATH
P3=$(which python3)
P3=$(readlink -f ${P3})
unset LIBRARY_PATH PYTHONPATH
export LD_LIBRARY_PATH=${P3%/bin/python3*}/lib:${LD_LIBRARY_PATH}
LD_LIBRARY_PATH=${LD_LIBRARY_PATH%:}
### Installing asm in a Virtual Envionment. 
if [[ -d ~/.local/share/asm ]]; then
  rm -rf ~/.local/share/asm.bak
  echo "Renaming existing asm install to ~/.local/share/asm.bak "
  mv ~/.local/share/asm ~/.local/share/asm.bak
fi
printf "Installing virtual environment ~/.local/share/asm ... "
mkdir -p ~/.local/share/asm
mkdir -p ~/.local/bin
export VIRTUAL_ENV_DISABLE_PROMPT=1
# Check if 'ensurepip' is available, or use old virtualenv
if python3 -c "import ensurepip" &> /dev/null; then
  python3 -m venv ~/.local/share/asm
else
  python3 -m pip install --upgrade virtualenv
  python3 -m virtualenv ~/.local/share/asm
fi
###
source ~/.local/share/asm/bin/activate
echo "Done!"
echo "Installing packages required by asm ... "
curl -Ls https://raw.githubusercontent.com/dirkpetersen/asm/main/requirements.txt \
        -o ~/.local/share/asm/requirements.txt \
      && python3 -m pip --disable-pip-version-check \
         install --upgrade -r ~/.local/share/asm/requirements.txt
echo "Done!"

asm_update

~/.local/bin/asm --help
echo -e "\n\n  asm installed! Run 'asm --help' or this order of commands:\n"
echo "  asm config"
echo "  asm launch"
                        
deactivate

# check if there is a folder in PATH inside my home directory, deactivated 
#DIR_IN_PATH=$(IFS=:; for dir in $PATH; do if [[ $dir == $HOME* ]]; then echo $dir; break; fi; done)

if [[ ":$PATH:" == *":$HOME/.local/bin:"* ]]; then
  echo ""
  #echo "  ~/local/bin is in PATH, you can start 'asm'" 
else
  echo "export PATH=\$PATH:~/.local/bin" >> "${HOME}/.bashrc"
  echo ""
  echo "  ~/.local/bin added to PATH in .bashrc"
  echo "  Please logout/login again or run: source ~/.bashrc"
fi