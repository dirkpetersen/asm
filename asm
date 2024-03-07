#! /bin/bash

ALTPYTHON=/home/exacloud/software/spack/opt/spack/linux-centos7-ivybridge/gcc-8.3.1/python-3.10.8-lgmermnb2kmzendjw24fftlpxwpaokdm/bin/python3
PMIN="8" # python3 minor version = 3.8

script_path="$(readlink -f "$0")"
script_dir="$(dirname "$script_path")"
umask 0002

if [[ $1 == "update" ]]; then
  curl -s https://raw.githubusercontent.com/dirkpetersen/asm/main/install.sh?token=$(date +%s) | bash -s -- update
  exit 0
fi
if [[ -d ~/.local/share/asm/bin ]]; then
  export VIRTUAL_ENV_DISABLE_PROMPT=1
  source ~/.local/share/asm/bin/activate
  PY3=$(which python3)
  PY3=$(readlink -f ${PY3})
  unset LIBRARY_PATH PYTHONPATH
  export LD_LIBRARY_PATH=${PY3%/bin/python3*}/lib:${LD_LIBRARY_PATH}
  LD_LIBRARY_PATH=${LD_LIBRARY_PATH%:}
  python3 ${script_dir}/asm.py "$@"
  deactivate
else
  if [[ -e ${ALTPYTHON} ]]; then
    ${ALTPYTHON} ${script_dir}/asm.py "$@"
  else
    # Check if we have at least the minimum Python version 
    if [[ $(/usr/bin/python3 -c "import sys; print(sys.version_info >= (3,${PMIN}))") == "True" ]]; then
      /usr/bin/python3 ${script_dir}/asm.py "$@"
    else
      echo "Python version must be greater than or equal to 3.${PMIN}"
    fi
  fi
fi