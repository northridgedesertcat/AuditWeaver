# rule matching data-model
## input data
RawLog:
```
{
   "event_id": "uuid-string",                    // string (日志唯一标识)
   "ip": "192.168.164.29",                       // string (IP地址)
   "method": "GET",                              // string (HTTP方法)
   "path": "/profile",                           // string (请求路径)
   "http_version": "1.1",                        // string (HTTP版本)
   "status": 200,                                // integer (HTTP状态码)
   "bytes": 557,                                 // integer (响应字节数)
   "referrer": "http://example.com/index.html",  // string (来源URL)
   "user_agent": "Mozilla/5.0 (...)",            // string (用户代理)
   "log_timestamp": 1719763200000                // integer (epoch_millis, 日志时间戳)
}
```

## preprocessor
check the log structure and 
data-model.
output:
LogMessage
```json
{
   "event_id": "uuid-string", 
   "ip": "string",
   "method": "string", 
   "path": "string",
   "http_version": "string",
   "status": "integer",  
   "bytes": "integer", 
   "referrer": "string",
   "user_agent": "string",
   "log_timestamp": "int64"
}

```

example
```json
{
  "event_id": "8e5d2b17-11c6-4eb9-a6de-7d1e8b7b6f01",
  "ip": "192.168.164.29",
  "method": "GET",
  "path": "/profile",
  "http_version": "HTTP/1.1",
  "status": 200,
  "response_bytes": 557,
  "referrer": "http://example.com/index.html",
  "user_agent": "Mozilla/5.0 (...)",
  "log_timestamp": 1719763200000
}
```

## rule profile repository

```yaml
id: sql_injection
name: SQL Injection
description: Detect SQL Injection attacks.

enabled: true

# Which log fields should be analyzed
target_fields:
  - path
  - referrer

# Matchers executed in order
matchers:
  - type: regex
    library: sql_regex


```

## regex pattern repository
```yaml
id: sql_regex
name: SQL Injection Regex Repository
version: "1.0"
description: Regular expressions for SQL Injection detection.

patterns:

  - id: union_select
    enabled: true
    regex: '(?i)union\s+select'
    description: Detect UNION SELECT statement.

  - id: sleep_function
    enabled: true
    regex: '(?i)sleep\s*\('
    description: Detect MySQL sleep function.

  - id: benchmark_function
    enabled: true
    regex: '(?i)benchmark\s*\('
    description: Detect benchmark function.

  - id: information_schema
    enabled: true
    regex: '(?i)information_schema'
    description: Detect access to information_schema.

  - id: load_file
    enabled: true
    regex: '(?i)load_file\s*\('
    description: Detect MySQL load_file function.
```


## rule engine
Class: EventBuilder
model: SecurityEvent
```json
{
  "event_id": "UUID",
  "attack_type": "string"

  "detections": [
    {
      "rule_id": "string",
      "attack_type": "string",

      "matches": [
        {
          "field": "string",
          "pattern_id": "string",
          "matched_value": "string"
        }
      ]
    }
  ],

  "log_context": {
    "ip": "string",
    "method": "string",
    "path": "string",
    "normalized_path": "string",
    "http_version": "string",
    "status": "integer",
    "bytes": "integer",
    "referrer": "string",
    "user_agent": "string",
    "timestamp": "int64"
  }
}

```

```json
{
  "event_id": "uuid-string",
  "attack_type": "SQL_INJECTION",

  "detections": [

    {
      "rule_id": "sql_injection",

      "matches": [

        {
          "field": "path",

          "pattern_id": "union_select",

          "matched_value": "/search?id=' union select"
        },

        {
          "field": "path",

          "pattern_id": "sleep_function",

          "matched_value": "/search?id=sleep(5)"
        }

      ]
    }

  ],


  "log_context": {

    "ip": "192.168.1.10",

    "method": "GET",

    "path": "/search?id=%27%20union%20select",

    "normalized_path":
      "/search?id=' union select",

    "http_version": "HTTP/1.1",

    "status": 200,

    "bytes": 1024,

    "referrer": "",

    "user_agent": "Mozilla/5.0",

    "timestamp": 1720000000000

  }
}
```

class: RegexMatcher:
model: 
```json

```


## config
