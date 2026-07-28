# rule engine responsibilities design.

## kafka consumer

responsibility:
- consume data from kafka.
- send data to preprocessor

not responsible for:
- process the data.

input:
- Kafka Message

output:
- RawLog

## preprocessor

responsibility:
- normalize the data structure.
- check for missing required fields.
- decode encoded content including Double URL Encoding,HTML Entity Encoding,Unicode Escape.

input:
- RawLog

output:
- LogMessage

## Rule Engine

Responsibilities:
- Execute matching logic according to Rule Profile.
- Apply regex patterns to specified fields.
- Generate matching results.

Not responsible for:
- Defining detection rules.
- Managing regex libraries.

Input:
- LogMessage
- RuleProfile
- RegexPattern Repository

Output:
- MatchResult

## rule profile repository
responsibility:
- edit the yaml config file.
- Determine how rule engine should match the logs.
- Determine which regex pattern the rule engine should use.

## regex pattern repository
responsibility: 
- edit yaml regex files.
- Determine the regex rule engine should match.

## kafka producer
responsibility:
- send result to kafka.