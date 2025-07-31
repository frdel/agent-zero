### humanlayer_contact

manage and configure HumanLayer contact channels for approvals and consultations
validate configuration, test connectivity, and manage multi-channel communication setup
handles Slack, Email, and other contact methods with proper configuration validation

usage:

1 validate current HumanLayer configuration

~~~json
{
    "thoughts": [
        "I should check if HumanLayer is properly configured",
        "This will help identify any setup issues",
        "Validation before using approval/consultation tools"
    ],
    "headline": "Validating HumanLayer configuration",
    "tool_name": "humanlayer_contact",
    "tool_args": {
        "action": "validate"
    }
}
~~~

2 test contact channel connectivity

~~~json
{
    "thoughts": [
        "I want to verify the contact channel is working",
        "Testing will confirm humans can receive messages",
        "Better to test now before needing approval"
    ],
    "headline": "Testing contact channel connectivity",
    "tool_name": "humanlayer_contact",
    "tool_args": {
        "action": "test",
        "channel_type": "slack"
    }
}
~~~

3 list all configured contact channels

~~~json
{
    "thoughts": [
        "I need to see what contact channels are available",
        "This will show the configuration status",
        "Helpful for understanding communication options"
    ],
    "headline": "Listing configured contact channels",
    "tool_name": "humanlayer_contact",
    "tool_args": {
        "action": "list"
    }
}
~~~

4 configure new contact channel

~~~json
{
    "thoughts": [
        "I need to help set up a new contact channel",
        "This will provide configuration guidance",
        "Slack channel configuration for notifications"
    ],
    "headline": "Configuring new Slack contact channel",
    "tool_name": "humanlayer_contact",
    "tool_args": {
        "action": "configure",
        "channel_type": "slack",
        "channel_config": {
            "channel_id": "C1234567890",
            "context": "Engineering team approval channel"
        }
    }
}
~~~

5 configure email contact channel

~~~json
{
    "thoughts": [
        "Setting up email as backup contact method",
        "Email is good for formal approval requests",
        "Need to configure email address and settings"
    ],
    "headline": "Configuring email contact channel",
    "tool_name": "humanlayer_contact",
    "tool_args": {
        "action": "configure",
        "channel_type": "email",
        "channel_config": {
            "address": "admin@company.com",
            "subject": "Agent Zero Approval Request"
        }
    }
}
~~~

6 test specific contact channel type

~~~json
{
    "thoughts": [
        "I want to test email specifically",
        "This will verify email delivery works",
        "Important to test before production use"
    ],
    "headline": "Testing email contact channel",
    "tool_name": "humanlayer_contact",
    "tool_args": {
        "action": "test",
        "channel_type": "email"
    }
}
~~~