### humanlayer_approval

request human approval for sensitive operations before execution
use when AI needs human oversight or validation for high-stakes actions
specify clear operation description and context for informed human decision
handles approval/denial responses and timeout scenarios gracefully
blocks execution until human approval received through configured contact channels

usage:

1 request approval for file deletion operation

~~~json
{
    "thoughts": [
        "I need to delete some files that could be important",
        "This is a potentially dangerous operation",
        "I should get human approval before proceeding"
    ],
    "headline": "Requesting human approval for file deletion",
    "tool_name": "humanlayer_approval",
    "tool_args": {
        "operation": "Delete backup files from /tmp/backups/",
        "context": "These files appear to be old backup files from last month, but I want to confirm before deletion",
        "timeout": 300
    }
}
~~~

2 request approval for system configuration changes

~~~json
{
    "thoughts": [
        "The user wants me to modify system configuration",
        "This could affect system stability",
        "I need human approval for this change"
    ],
    "headline": "Requesting approval for system configuration change",
    "tool_name": "humanlayer_approval",
    "tool_args": {
        "operation": "Modify nginx configuration to add new virtual host",
        "context": "Adding SSL configuration for new domain example.com with port 443 redirect",
        "timeout": 600
    }
}
~~~

3 request approval with specific contact channel

~~~json
{
    "thoughts": [
        "This is a critical database operation",
        "I need approval from the database admin specifically",
        "I should use email for this formal request"
    ],
    "headline": "Requesting DBA approval for database schema change",
    "tool_name": "humanlayer_approval",
    "tool_args": {
        "operation": "Drop unused table 'legacy_orders' from production database",
        "context": "Table has been deprecated for 6 months, confirmed no foreign key references, but want DBA confirmation",
        "contact_channel": "email",
        "timeout": 900
    }
}
~~~

4 request approval for code execution with security implications

~~~json
{
    "thoughts": [
        "This code involves network access and file system operations",
        "It could have security implications",
        "Human approval required for execution"
    ],
    "headline": "Requesting approval for potentially risky code execution",
    "tool_name": "humanlayer_approval",
    "tool_args": {
        "operation": "Execute script that downloads and installs software packages",
        "context": "Script will: 1) Download packages from external repo, 2) Install with sudo privileges, 3) Modify system PATH"
    }
}
~~~