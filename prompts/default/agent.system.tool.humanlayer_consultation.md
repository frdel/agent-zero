### humanlayer_consultation

ask humans questions to get expert advice and contextual guidance
use when AI needs human expertise, domain knowledge, or complex decision input
provide clear questions with sufficient context for informed human responses
handles timeout scenarios gracefully and continues with available information

usage:

1 consult human for technical decision

~~~json
{
    "thoughts": [
        "I need to choose between two different approaches",
        "This requires domain expertise I don't have",
        "A human expert could provide valuable guidance"
    ],
    "headline": "Consulting human expert for technical approach",
    "tool_name": "humanlayer_consultation",
    "tool_args": {
        "question": "Should I use REST API or GraphQL for this new service integration?",
        "context": "Building integration with external payment service. Current system uses REST, but GraphQL might be more efficient for complex queries. Performance and maintainability are key concerns."
    }
}
~~~

2 seek human guidance for business logic decision

~~~json
{
    "thoughts": [
        "This involves business rules I'm not certain about",
        "The requirements could be interpreted different ways",
        "Human input would clarify the intended behavior"
    ],
    "headline": "Seeking clarification on business requirements",
    "tool_name": "humanlayer_consultation",
    "tool_args": {
        "question": "How should the system handle customers with expired subscriptions trying to access premium features?",
        "context": "Current code shows mixed handling - some features show grace period, others block immediately. Need consistent policy for user experience.",
        "timeout": 450
    }
}
~~~

3 consult on code review and best practices

~~~json
{
    "thoughts": [
        "I've written some complex code",
        "A human review could catch issues I missed",
        "Best practices input would be valuable"
    ],
    "headline": "Requesting code review and best practices advice",
    "tool_name": "humanlayer_consultation",
    "tool_args": {
        "question": "Is this authentication implementation secure and following best practices?",
        "context": "Implemented JWT with refresh tokens, rate limiting, and bcrypt password hashing. Using Redis for session storage. Code handles token expiration and refresh automatically."
    }
}
~~~

4 ask for creative input or brainstorming

~~~json
{
    "thoughts": [
        "This problem needs creative problem-solving",
        "Human creativity could provide innovative solutions",
        "Multiple perspectives would be helpful"
    ],
    "headline": "Seeking creative input for problem solving",
    "tool_name": "humanlayer_consultation",
    "tool_args": {
        "question": "What are some creative ways to improve user engagement with our notification system?",
        "context": "Current email notifications have low open rates (12%). Users complain about too many emails but miss important updates. Looking for innovative approaches to balance communication and user satisfaction.",
        "contact_channel": "slack"
    }
}
~~~

5 consult on data interpretation and analysis

~~~json
{
    "thoughts": [
        "The data shows unexpected patterns",
        "Human interpretation could explain the anomalies",
        "Domain expertise needed for proper analysis"
    ],
    "headline": "Consulting on unexpected data patterns",
    "tool_name": "humanlayer_consultation",
    "tool_args": {
        "question": "What might explain the 40% spike in API errors on weekends compared to weekdays?",
        "context": "Error logs show increased timeout errors and connection failures on Saturdays/Sundays. No apparent system changes or increased load. Weekend traffic is typically 30% lower than weekdays."
    }
}
~~~