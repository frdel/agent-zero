# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
    . /etc/bashrc
fi

# Activate the virtual environment
source /opt/venv/bin/activate

# Change to the desired work directory upon SSH login
cd /home/agent-zero/work_dir