"""HTTP and JSON activity generators."""
from ._helpers import _hs, _uuid, _escape_xml_attr, _escape_vb_expr
from ._xml_utils import _viewstate_block


def gen_net_http_request(method, request_url_variable, result_variable, id_ref,
                         display_name="HTTP Request",
                         auth_type="None", oauth_token_variable="",
                         text_payload_variable="",
                         content_type="application/json",
                         headers_expr="",
                         parameters_expr="",
                         timeout_ms=30000,
                         retry_count=3,
                         retry_policy="Exponential",
                         indent="    "):
    """Generate NetHttpRequest — NO RetryScope needed (has built-in retry).

    NetHttpRequest has built-in RetryCount, RetryPolicyType, and RetryStatusCodes
    properties. Wrapping in RetryScope would cause redundant double-retry.

    Hallucination patterns prevented:
    - Wrong namespace (must be uwah:, not ui: or default)
    - Missing {x:Null} for unused properties (causes crash)
    - Missing FormDataParts default expression
    - Missing RetryStatusCodes list
    - Hardcoded URLs (lint catches — must use variable/Config)
    - Missing HttpResponseSummary variable type
    - Wrong property names (RequestURL vs RequestUrl, Body vs TextPayload)
    - Wrapping in RetryScope (redundant — activity retries internally)

    Requires namespaces in file header:
        xmlns:uwah="clr-namespace:UiPath.Web.Activities.Http;assembly=UiPath.Web.Activities"
        xmlns:uwahm="clr-namespace:UiPath.Web.Activities.Http.Models;assembly=UiPath.Web.Activities"

    Requires variable: <Variable x:TypeArguments="uwahm:HttpResponseSummary" Name="{result_variable}" />

    Args:
        method: "GET", "POST", "PUT", "PATCH", "DELETE"
        request_url_variable: VB expression for URL (no brackets), e.g. 'in_strApiEndpoint'
        result_variable: Variable to receive HttpResponseSummary (no brackets)
        id_ref: Base IdRef number
        auth_type: "None", "OAuthToken", "BasicAuth"
        oauth_token_variable: Variable name for OAuth token (when auth_type="OAuthToken")
        text_payload_variable: VB expression for request body (POST/PUT/PATCH)
        content_type: MIME type for payload
        headers_expr: VB expression for headers dict, or empty for {x:Null}
        parameters_expr: VB expression for URL parameters dict, or empty for {x:Null}
        timeout_ms: Request timeout in milliseconds
        retry_count: Built-in retry count (default 3). Set 0 to disable.
        retry_policy: "Exponential" (default), "Linear", or "None"
    """
    if not (method in ("GET", "POST", "PUT", "PATCH", "DELETE")):
        raise ValueError(f"Invalid method: {method}")
    if not (auth_type in ("None", "OAuthToken", "BasicAuth")):
        raise ValueError(f"Invalid auth_type: {auth_type}")
    if not (retry_policy in ("Exponential", "Linear", "None")):
        raise ValueError(f"Invalid retry_policy: {retry_policy}")

    dn = _escape_xml_attr(display_name)
    i, i2 = indent, indent + "  "

    # Null properties — all must be present or Studio shows warnings
    null_props = [
        "BasicAuthPassword", "BasicAuthSecurePassword", "BasicAuthUsername",
        "BinaryPayload", "ClientCertPassword", "ClientCertPath",
        "ClientCertSecurePassword", "Cookies", "CustomNegotiatedAuthCredentials",
        "FilePath", "FormData", "LocalFiles", "OutputFileName",
        "OutputFileTargetFolder", "PathResource", "ProxyConfiguration", "ResourceFiles",
    ]
    null_attrs = " ".join(f'{p}="{{x:Null}}"' for p in null_props)

    # Conditional attributes
    oauth = f'OAuthToken="[{_escape_vb_expr(oauth_token_variable)}]"' if auth_type == "OAuthToken" else 'OAuthToken="{x:Null}"'
    headers = f'Headers="[{_escape_xml_attr(headers_expr)}]"' if headers_expr else 'Headers="{x:Null}"'
    params = f'Parameters="[{_escape_xml_attr(parameters_expr)}]"' if parameters_expr else 'Parameters="{x:Null}"'
    payload = f'TextPayload="[{_escape_vb_expr(text_payload_variable)}]"' if text_payload_variable else 'TextPayload=""'

    form_data_parts = ('FormDataParts="[New List (Of FormDataPart) From _'
                       '&#xA;{&#xA;&#x9;New FileFormDataPart(),&#xA;&#x9;'
                       'New BinaryFormDataPart(),&#xA;&#x9;New TextFormDataPart()'
                       '&#xA;}]"')

    retry_codes = ('RetryStatusCodes="[New List (Of System.Net.HttpStatusCode) From _'
                   '&#xA;{&#xA;&#x9;System.Net.HttpStatusCode.RequestTimeout,'
                   '&#xA;&#x9;System.Net.HttpStatusCode.TooManyRequests,'
                   '&#xA;&#x9;System.Net.HttpStatusCode.InternalServerError,'
                   '&#xA;&#x9;System.Net.HttpStatusCode.BadGateway,'
                   '&#xA;&#x9;System.Net.HttpStatusCode.ServiceUnavailable,'
                   '&#xA;&#x9;System.Net.HttpStatusCode.GatewayTimeout'
                   '&#xA;}]"')

    return (
        f'{i}<uwah:NetHttpRequest {null_attrs} '
        f'{oauth} {headers} {params} '
        f'AuthenticationType="{auth_type}" ContinueOnError="True" '
        f'DisableSslVerification="False" '
        f'DisplayName="{dn}" '
        f'EnableCookies="True" FileOverwrite="AutoRename" FollowRedirects="True" '
        f'{form_data_parts} '
        f'InitialDelay="500" MaxRedirects="3" MaxRetryAfterDelay="30000" '
        f'Method="{method}" Multiplier="2" '
        f'PreferRetryAfterValue="True" RequestBodyType="Text" '
        f'RequestUrl="[{_escape_vb_expr(request_url_variable)}]" Result="[{_escape_vb_expr(result_variable)}]" '
        f'RetryCount="{retry_count}" RetryPolicyType="{retry_policy}" '
        f'{retry_codes} '
        f'SaveRawRequestResponse="False" SaveResponseAsFile="False" '
        f'{payload} TextPayloadContentType="{content_type}" '
        f'TextPayloadEncoding="UTF-8" TlsProtocol="Automatic" '
        f'UseJitter="True" UseOsNegotiatedAuthCredentials="False" '
        f'{_hs("NetHttpRequest")} '
        f'sap2010:WorkflowViewState.IdRef="NetHttpRequest_{id_ref}">\n'
        f'{i2}<uwah:NetHttpRequest.TimeoutInMiliseconds>\n'
        f'{i2}  <InArgument x:TypeArguments="s:Nullable(x:Int32)">\n'
        f'{i2}    <Literal x:TypeArguments="s:Nullable(x:Int32)" Value="{timeout_ms}" />\n'
        f'{i2}  </InArgument>\n'
        f'{i2}</uwah:NetHttpRequest.TimeoutInMiliseconds>\n'
        f'{i}</uwah:NetHttpRequest>'
    )


def gen_deserialize_json(json_string_variable, output_variable, id_ref,
                         type_argument="njl:JObject",
                         display_name="Deserialize JSON", indent="    "):
    """Generate DeserializeJson — JSON string to object.

    Hallucination patterns prevented:
    - Wrong namespace (must be ui:DeserializeJson, not default ns)
    - Wrong TypeArguments (model invents custom types)
    - Wrong property names (JsonInput vs JsonString, Output vs JsonObject)
    - Missing Settings="{x:Null}"

    Requires namespace: xmlns:njl="clr-namespace:Newtonsoft.Json.Linq;assembly=Newtonsoft.Json"

    Args:
        json_string_variable: VB expression for input JSON string (no brackets)
        output_variable: Output variable name (no brackets)
        id_ref: Base IdRef number
        type_argument: Output type — "njl:JObject" (most common), "njl:JArray", etc.
    """
    dn = _escape_xml_attr(display_name)
    i = indent

    return (
        f'{i}<ui:DeserializeJson x:TypeArguments="{type_argument}" Settings="{{x:Null}}" '
        f'DisplayName="{dn}" '
        f'{_hs("DeserializeJson")} '
        f'sap2010:WorkflowViewState.IdRef="DeserializeJson_{id_ref}" '
        f'JsonObject="[{_escape_vb_expr(output_variable)}]" '
        f'JsonSample="" '
        f'JsonString="[{_escape_vb_expr(json_string_variable)}]" />'
    )
