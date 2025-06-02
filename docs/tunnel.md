# Agent Zero Tunnel Feature

The tunnel feature in Agent Zero allows you to expose your local Agent Zero instance to the internet using Flaredantic tunnels. This makes it possible to share your Agent Zero instance with others without requiring them to install and run Agent Zero themselves.

## How It Works

Agent Zero uses the [Flaredantic](https://pypi.org/project/flaredantic/) library to create secure tunnels to expose your local instance to the internet. These tunnels:

- Are secure (HTTPS)
- Don't require any configuration
- Generate unique URLs for each session
- Can be regenerated on demand

## Using the Tunnel Feature

1. Open the settings and navigate to the "External Services" tab
2. Click on "Flare Tunnel" in the navigation menu
3. Click the "Create Tunnel" button to generate a new tunnel
4. Once created, the tunnel URL will be displayed and can be copied to share with others
5. The tunnel URL will remain active until you stop the tunnel or close the Agent Zero application

## Security Considerations

When sharing your Agent Zero instance via a tunnel:

- Anyone with the URL can access your Agent Zero instance
- No additional authentication is added beyond what your Agent Zero instance already has
- Consider setting up authentication if you're sharing sensitive information
- The tunnel exposes your local Agent Zero instance, not your entire system

## Troubleshooting

If you encounter issues with the tunnel feature:

1. Check your internet connection
2. Try refreshing the tunnel URL
3. Restart Agent Zero
4. Check the console logs for any error messages

## Adding Authentication

To add basic authentication to your Agent Zero instance when using tunnels, you can set the following environment variables:

```
AUTH_LOGIN=your_username
AUTH_PASSWORD=your_password
```

Alternatively, you can configure the username and password directly in the settings:

1. Open the settings modal in the Agent Zero UI
2. Navigate to the "External Services" tab
3. Find the "Authentication" section
4. Enter your desired username and password in the "UI Login" and "UI Password" fields
5. Click the "Save" button to apply the changes

This will require users to enter these credentials when accessing your tunneled Agent Zero instance. When attempting to create a tunnel without authentication configured, Agent Zero will display a security warning.