This directory is an include directory for the supervisord config files defined by the user/agent.
Placing supervisord config files in this directory with .conf extension will include them in the supervisord config. This way you can start additional user-defined services with the container. Useful for example if an mcp server needs some extra service to run.

After placing a config in the specified directory restart the container and the services should become active if there are no startup errors. If there are errors, check the docker logs for more information.

If you also ship scripts for the custom services, do not forget to make them executable or call them with bash command explicitly.

The config files are expected to be in the following format:

[program:my_program]
command=/a0/supervisor.conf.d/my_program.sh
directory=/a0/share/mcp/my_program
autostart=true
autorestart=true
environment=PYTHONPATH=/a0,PYTHONUNBUFFERED=1,PYTHONIOENCODING=utf-8
stopwaitsecs=1
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
autorestart=true
startretries=3
stopasgroup=true
killasgroup=true
