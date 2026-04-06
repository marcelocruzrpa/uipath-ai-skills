# Orchestrator & Services

GetRobotAsset, GetRobotCredential, AddQueueItem, GetQueueItem, SetTransactionStatus, HTTP Request. Tasks (CreateFormTask, WaitForFormTask) → **decoupled to uipath-tasks skill**.

## Contents
  - [Get Robot Asset (GetRobotAsset)](#get-robot-asset-getrobotasset)
  - [Get Credential (GetRobotCredential)](#get-credential-getrobotcredential)
  - [Add Queue Item (AddQueueItem)](#add-queue-item-addqueueitem)
  - [Get Queue Item (GetQueueItem)](#get-queue-item-getqueueitem)
  - [Set Transaction Status (SetTransactionStatus)](#set-transaction-status-settransactionstatus)
  - [HTTP Request (NetHttpRequest)](#http-request-nethttprequest)
- [Tasks Activities (Form Tasks)](#tasks-activities-form-tasks) → **Decoupled to uipath-tasks skill**


### Get Robot Asset (GetRobotAsset)
Retrieves a **non-credential** config value from Orchestrator (URLs, folder paths, feature flags, thresholds).
→ **Use `gen_get_robot_asset()`** — generates correct XAML deterministically.

Properties:
- `AssetName` — name of the Orchestrator asset (string literal, not VB expression)
- `CacheStrategy`: `None` (always fetch), `PerRobot`, `Global`
- `TimeoutMS="{x:Null}"` — no timeout (use default)
- Output: element syntax `.Value` with `OutArgument` — type matches asset type: `x:String`, `x:Int32`, `x:Boolean`
- **⚠️ Output property is `.Value` (element syntax), NOT `Result`.** `Result` does not exist — Studio crashes with `Could not find member 'Result'`. Must use: `<ui:GetRobotAsset.Value><OutArgument x:TypeArguments="x:String">[var]</OutArgument></ui:GetRobotAsset.Value>`

**⚠️ Do NOT use GetRobotAsset for credentials (passwords, API keys, secrets, tokens).** Use `GetRobotCredential` instead — it stores secrets as SecureString and returns username + password in a single call from a Credential asset type.

### Get Credential (GetRobotCredential)
Use for **any credential pair**: login credentials, API client ID + secret, tokens, service accounts. Returns Username (String) + Password (SecureString) from a single Orchestrator Credential asset.
→ **Use `gen_getrobotcredential()`** — generates correct XAML deterministically.


**⚠️ CRITICAL — common hallucinations:**
- **`Result=` does NOT exist** on this activity — Studio crashes with "Could not find member 'Result'". Use `Password=` and `Username=` attributes directly.
- **Password is SecureString** — the variable must be declared as `ss:SecureString`, not `x:String`. Use `SecureText=` (not `Text=`) on NTypeInto for password fields.
- **Retrieve inside NApplicationCard** (minimal scope) — do NOT place GetRobotCredential outside the browser/app session. See golden sample `WebAppName_Launch.xaml`.
- **Wrap in RetryScope** — Orchestrator API calls can transiently fail. See golden sample.
- **AssetName from argument** — pass `in_strCredentialAssetName` from Config, never hardcode `AssetName="WebApp_Credential"`.

Properties:
- `AssetName` — Orchestrator Credential asset name (string literal or VB expression)
- `Username` — OutArgument `x:String` (e.g. API client ID, login username, service account)
- `Password` — OutArgument `SecureString` (e.g. API secret, password, token)
- `CacheStrategy`: `None` (always fetch), `Execution` (cache per run), `Global`
- Password is SecureString — convert to plain text only when needed: `New System.Net.NetworkCredential("", secstrPassword).Password`

Examples of what goes in Credential assets:
- Login credentials → Username = `"user@example.com"`, Password = password
- API auth → Username = client_id, Password = client_secret
- Service account → Username = account name, Password = API key/token

**❌ WRONG:** Two separate `GetRobotAsset` calls for username and password — stores secrets as plain text assets.

**✅ RIGHT:** One `GetRobotCredential` call — retrieves both username and SecureString password from a single Credential asset.
→ **Use `gen_getrobotcredential()`** — generates correct XAML deterministically.


### Add Queue Item (AddQueueItem)

Adds a new item to an Orchestrator queue with custom data fields. Used in dispatcher workflows to populate queues for performer bots.

→ **Use `gen_add_queue_item()`** — generates correct XAML deterministically.

Properties:
- `QueueType` — queue name in Orchestrator (VB.NET expression). **⚠️ Property is `QueueType`, NOT `QueueName`** — `QueueName` does not exist and crashes Studio. Common hallucination because Config key is `OrchestratorQueueName` and model field is `queue_name`. Lint 54.
- `FolderPath` — Orchestrator folder path. Use `{x:Null}` for default folder
- `Reference` — unique transaction reference string (for deduplication / tracking)
- `Priority`: `Normal`, `High`, `Low`
- `ServiceBaseAddress="{x:Null}"` — uses robot's default Orchestrator connection
- `TimeoutMS="{x:Null}"` — default timeout
- **`.ItemInformation` child** — dictionary of key-value pairs (queue item specific content). Each entry is `<InArgument x:TypeArguments="x:String" x:Key="FieldName">[value]</InArgument>`. All values must be strings — convert non-strings with `.ToString`

**⚠️ CRITICAL — `ItemInformation` vs `SpecificContent`:**
- **WRITING** (AddQueueItem in XAML): property is `<ui:AddQueueItem.ItemInformation>` — ⛔ NOT `SpecificContent`
- **READING** (VB.NET expressions at runtime): property is `TransactionItem.SpecificContent("Key")`
- Using `SpecificContent` in XAML causes: `Could not find member 'SpecificContent'` → activity becomes UnresolvedActivity

**⚠️ RESERVED KEY NAMES:** Do NOT use these as `x:Key` in ItemInformation — they conflict with AddQueueItem's built-in properties and cause "RuntimeArgument already exists" errors: `DueDate`, `DeferDate`, `Reference`, `Priority`. Use prefixed names instead (e.g. `InvoiceDueDate`, `ItemPriority`).

**⚠️ WRONG ELEMENT TYPE:** Entries must be `<InArgument x:TypeArguments="x:String" x:Key="...">` — ⛔ NOT `<x:String x:Key="...">`. Using `x:String` causes: `x:String is not assignable to Dictionary(String,InArgument)` → activity becomes ErrorActivity.

**⚠️ WRONG DICTIONARY PATTERN:** ItemInformation entries are flat `<InArgument>` elements directly under `.ItemInformation` — ⛔ NOT wrapped in `<scg:Dictionary x:TypeArguments="x:String, InArgument">` (Studio accepts both, but emits flat). ⛔ And definitely NOT a single `<InArgument x:TypeArguments="scg:Dictionary(x:String, x:Object)">` wrapping a `New Dictionary(...)` VB expression — that crashes Studio with `Missing key value on 'InArgument' object`.

**⚠️ WRONG TYPE NAME:** ⛔ NOT `<scg:Dictionary x:TypeArguments="x:String, Argument">` — `Argument` type does not exist. Correct is `InArgument`. Crashes: `Could not resolve type 'Dictionary(String,Argument)'`.

**⚠️ WRONG NAMESPACE PREFIX:** ⛔ NOT `<ui:InArgument>` — `InArgument` is in the default XAML activities namespace, not `ui:`. Crashes: `Could not find type 'InArgument(String)' in namespace 'http://schemas.uipath.com/workflow/activities'`. Use `<InArgument>` (no prefix).

### Get Queue Item (GetQueueItem)

Retrieves the next available item from an Orchestrator queue. Returns Nothing when the queue is empty.

→ **Use `gen_get_queue_item()`** — generates correct XAML deterministically.

Properties:
- `QueueType` — queue name
- `FolderPath` — Orchestrator folder
- `TransactionItem` — output variable of type `ui:QueueItem`
- `.Reference` — optional: filter by specific reference string (empty = next available)
- `.TimeoutMS` — empty = default
- **Check for empty queue:** `[TransactionItem Is Nothing]` — standard REFramework pattern to detect when all items are processed

**Accessing QueueItem fields (SpecificContent):**
```vb
' Get a field value (returns Object — cast with .ToString)
in_TransactionItem.SpecificContent("FieldName").ToString

' Iterate all fields
For Each item In in_TransactionItem.SpecificContent   ' KeyValuePair(String, Object)
  item.Key    ' field name
  item.Value  ' field value
```
The `ui:ForEach` over SpecificContent uses: `x:TypeArguments="scg:KeyValuePair(x:String, x:Object)"`

### Set Transaction Status (SetTransactionStatus)

Updates the status of a queue item in Orchestrator. Three usage patterns: Success, Business Exception (won't retry), System Exception (will retry).

> ⛔ **NEVER modify `SetTransactionStatus.xaml`.** It is a framework file handled entirely by the REFramework template. No generator needed — the scaffold provides it.

**Status values:** `Successful`, `Failed`

**ErrorType values:** `Business` (won't retry — data/rule issue), `Application` (will retry — system/infra issue)

Properties:
- `Status` + `ErrorType` — determine retry behavior
- `Reason` — error message VB expression (e.g., `[in_BusinessException.Message]`). Set for failed transactions
- `Details` — additional info (e.g., screenshot path). Optional
- `TransactionItem` — the QueueItem to update
- `.Analytics`, `.Output` — dictionaries (usually empty but required as child elements)
- **Always wrap in RetryScope + TryCatch** — Orchestrator calls can fail transiently

### HTTP Request (NetHttpRequest)

Requires NuGet: `UiPath.WebAPI.Activities`. Response variable type: `uwahm:HttpResponseSummary`.

#### POST with OAuth Token Authentication
```json
{
  "gen": "net_http_request",
  "args": {
    "method": "POST",
    "request_url_variable": "in_strApiEndpoint",
    "result_variable": "httpReqResponse",
    "auth_type": "OAuthToken",
    "oauth_token_variable": "strApiAccessToken",
    "text_payload_variable": "in_strApiBody",
    "content_type": "application/json",
    "parameters_expr": "new Dictionary(Of String, String) From {{ \"externalId\", in_strApiExternalIdParam }}",
    "timeout_ms": 10000,
    "retry_count": 3,
    "display_name": "HTTP Request (API - Create Record)"
  }
}
```

#### GET Request
```json
{
  "gen": "net_http_request",
  "args": {
    "method": "GET",
    "request_url_variable": "strApiEndpoint",
    "result_variable": "obj_httpResponse",
    "timeout_ms": 30000,
    "display_name": "HTTP Request (GET - API Endpoint)"
  }
}
```

The generator handles all `{x:Null}` boilerplate props (~15), `FormDataParts`, `RetryStatusCodes` list, `TimeoutInMiliseconds` child element (note: the typo is real — UiPath's actual property name), and namespace wiring.

#### Key Properties
- `Method`: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`
- `RequestUrl` — VB.NET expression for endpoint URL
- `Result` — `uwahm:HttpResponseSummary` variable
- `TextPayload` — request body as VB.NET string expression
- `TextPayloadContentType`: `application/json`, `application/x-www-form-urlencoded`, `text/xml`
- `ContinueOnError="True"` — common on HTTP calls to handle errors in workflow logic (check StatusCode) rather than throwing
- `FileOverwrite="AutoRename"` — rename strategy when downloading files that already exist
- Timeout uses Nullable(Int32) child element (milliseconds) — note typo: `TimeoutInMiliseconds`
- Many `{x:Null}` attributes are **required** — omitting them causes validation warnings

#### Authentication Types
- `AuthenticationType="None"` — no auth, `OAuthToken="{x:Null}"`
- `AuthenticationType="OAuthToken"` — OAuth bearer token: `OAuthToken="[strToken]"`
- `AuthenticationType="Basic"` — basic auth: `BasicAuthUsername="[strUser]"` + `BasicAuthPassword="[strPass]"`
- `AuthenticationType="OsNegotiatedAuth"` — Windows/NTLM: `UseOsNegotiatedAuthCredentials="True"`

#### Query Parameters (URL ?key=value pairs)
```vb
' Empty parameters
Parameters="{x:Null}"

' Single parameter — inline Dictionary
Parameters="[new System.Collections.Generic.Dictionary(Of System.String, System.String) From { { &quot;externalId&quot;, strIdParam } }]"

' Multiple parameters
Parameters="[new System.Collections.Generic.Dictionary(Of System.String, System.String) From { { &quot;page&quot;, intPage.ToString }, { &quot;limit&quot;, &quot;100&quot; } }]"
```

#### Custom Headers
```vb
' Empty headers (still requires Dict initialization in some exports)
Headers="[new System.Collections.Generic.Dictionary(Of System.String, System.String) From {  }]"
Headers="{x:Null}"

' With custom headers
Headers="[new System.Collections.Generic.Dictionary(Of System.String, System.String) From { { &quot;X-Custom-Header&quot;, &quot;value&quot; }, { &quot;Accept&quot;, &quot;application/json&quot; } }]"
```

#### Retry Configuration
- `RetryCount` — number of retries (0 = no retry)
- `RetryPolicyType`: `None`, `Basic`, `Exponential`
- `InitialDelay` — ms before first retry (for Exponential: base delay)
- `Multiplier` — exponential backoff multiplier (e.g., 2 = double each retry)
- `UseJitter` — randomize retry delays to avoid thundering herd
- `RetryStatusCodes` — VB.NET List of HttpStatusCode enum values that trigger retry:
```vb
' Standard retryable status codes
[New List (Of System.Net.HttpStatusCode) From _
{
  System.Net.HttpStatusCode.RequestTimeout,
  System.Net.HttpStatusCode.TooManyRequests,
  System.Net.HttpStatusCode.InternalServerError,
  System.Net.HttpStatusCode.BadGateway,
  System.Net.HttpStatusCode.ServiceUnavailable,
  System.Net.HttpStatusCode.GatewayTimeout
}]
```

#### FormDataParts (for multipart/form-data requests)
```vb
' Default empty form data parts (always present in exports even if unused)
[New List (Of FormDataPart) From _
{
  New FileFormDataPart(),
  New BinaryFormDataPart(),
  New TextFormDataPart()
}]
```

#### Response Handling
```vb
' Response body as string
httpReqResponse.TextContent

' HTTP status code (integer)
httpReqResponse.StatusCode

' Common pattern: fetch response into output variables
out_intStatusCode = httpReqResponse.StatusCode
out_strResponseBody = httpReqResponse.TextContent

' Parse JSON response
JObject.Parse(httpReqResponse.TextContent)("data")("id").ToString

' Check success
httpReqResponse.StatusCode >= 200 AndAlso httpReqResponse.StatusCode < 300
```

#### Typical API Call Pattern (OAuth Flow)
Real-world sequence from clipboard export:
```
1. LogMessage  → "[START] Create record via API"
2. InvokeWorkflowFile → fetch OAuth token workflow
     in_OAuthCredentialsAssetName = config("OAuth2_ClientCredentials").ToString
     in_OAuthGetAccessTokenEndpoint = config("OAuth2_GetAccessToken_Endpoint").ToString
     in_OAuthGetAccessTokenBody = config("OAuth2_GetAccessToken_Body").ToString
     out_strApiAccessToken → [strApiAccessToken]
3. LogMessage  → "Sending API request..."
4. NetHttpRequest → POST with OAuthToken="[strApiAccessToken]"
     ContinueOnError="True" (handle errors in workflow, not exception)
     → [httpReqResponse]
5. LogMessage  → "Fetching API request response data..."
6. Assign → httpReqResponse.TextContent → [out_strRequestMsgDetails]
7. Assign → httpReqResponse.StatusCode → [out_intStatusCode]
8. LogMessage  → "API request status code: " + out_intStatusCode.ToString
9. LogMessage  → "[END] Create record via API"
```
Notes:
- OAuth credentials stored as Orchestrator asset, endpoint/body in config dictionary
- `ContinueOnError="True"` prevents HTTP errors from throwing — check StatusCode instead
- Response extracted into Out arguments for caller to handle success/failure
- Log messages bracket the operation for traceability in Orchestrator logs


## Tasks Activities (Form Tasks)

> **→ Fully decoupled to dedicated skill: `uipath-tasks`**
>
> All Tasks code — generators, lint rules, scaffold hooks, and documentation — lives in `uipath-tasks/`. Loaded automatically via `plugin_loader.py`.
>
> Read `uipath-tasks/SKILL.md` and `uipath-tasks/references/tasks.md`.
