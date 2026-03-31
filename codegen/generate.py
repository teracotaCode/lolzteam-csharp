#!/usr/bin/env python3
"""
Code generator for Lolzteam C# API wrapper.
Reads OpenAPI 3.1 JSON and generates:
  - Response model classes (C# records with nullable init properties)
  - Enum types (string-backed with custom JsonConverter)
  - Client class with methods grouped by tags -> service classes
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from typing import Any

# ─── Naming Helpers ──────────────────────────────────────────────────────────

def pascal_case(s: str) -> str:
    """Convert any string to PascalCase."""
    if not s:
        return ""
    # Handle dot-separated like "Threads.Poll.Get" -> "ThreadsPollGet"
    parts = re.split(r'[._\-\s/]+', s)
    result = ""
    for part in parts:
        if not part:
            continue
        # Handle already-PascalCase or camelCase
        result += part[0].upper() + part[1:]
    return result


def camel_case(s: str) -> str:
    """Convert to camelCase."""
    if s and s[0].isdigit():
        s = 'p' + s
    p = pascal_case(s)
    if not p:
        return ""
    return p[0].lower() + p[1:]


def sanitize_name(s: str) -> str:
    """Remove characters invalid for C# identifiers."""
    s = re.sub(r'[^a-zA-Z0-9_]', '', s.replace('[]', 'Array'))
    if s and s[0].isdigit():
        s = '_' + s
    return s


def safe_param_name(name: str) -> str:
    """Convert API parameter name to safe C# parameter name."""
    clean = name.replace('[]', '').replace('[', '_').replace(']', '')
    result = camel_case(clean)
    # Prefix with _ if starts with digit
    if result and result[0].isdigit():
        result = '_' + result
    return result


def tag_to_class_name(tag: str) -> str:
    """Convert a tag name to a C# class name for the service."""
    return sanitize_name(pascal_case(tag)) + "Service"


def operation_to_method_name(operation_id: str) -> str:
    """Convert operationId to a C# method name.
    E.g. 'Threads.Poll.Get' -> 'PollGet', 'Categories.List' -> 'List'
    We strip the first segment (tag prefix) if there are multiple.
    """
    parts = operation_id.split('.')
    if len(parts) >= 2:
        # Drop first part (it's the tag/group name)
        return pascal_case('.'.join(parts[1:]))
    return pascal_case(operation_id)


def model_class_name(operation_id: str, method: str, suffix: str = "Response") -> str:
    """Generate a response model class name from operation id."""
    name = pascal_case(operation_id) + suffix
    return sanitize_name(name)


# ─── Type Mapping ────────────────────────────────────────────────────────────

# C# reserved words
CSHARP_RESERVED = {
    'abstract', 'as', 'base', 'bool', 'break', 'byte', 'case', 'catch',
    'char', 'checked', 'class', 'const', 'continue', 'decimal', 'default',
    'delegate', 'do', 'double', 'else', 'enum', 'event', 'explicit',
    'extern', 'false', 'finally', 'fixed', 'float', 'for', 'foreach',
    'goto', 'if', 'implicit', 'in', 'int', 'interface', 'internal',
    'is', 'lock', 'long', 'namespace', 'new', 'null', 'object', 'operator',
    'out', 'override', 'params', 'private', 'protected', 'public',
    'readonly', 'ref', 'return', 'sbyte', 'sealed', 'short', 'sizeof',
    'stackalloc', 'static', 'string', 'struct', 'switch', 'this', 'throw',
    'true', 'try', 'typeof', 'uint', 'ulong', 'unchecked', 'unsafe',
    'ushort', 'using', 'virtual', 'void', 'volatile', 'while'
}


def escape_identifier(name: str) -> str:
    if name in CSHARP_RESERVED:
        return '@' + name
    return name


def _is_dynamic_dict(schema: dict) -> bool:
    """Return True if the schema is an object whose property keys are ALL purely
    numeric — a telltale sign that the spec was generated from example data and
    the real shape is a dynamic dictionary keyed by ID."""
    if not isinstance(schema, dict):
        return False
    props = schema.get('properties', {})
    if not props:
        return False
    return all(re.match(r'^\d+$', k) for k in props.keys())


def openapi_type_to_csharp(schema: dict, components: dict, known_models: set) -> str:
    """Convert an OpenAPI schema to a C# type string. Always nullable."""
    if not schema:
        return "JsonElement?"

    ref = schema.get('$ref')
    if ref:
        ref_name = ref.split('/')[-1]
        # If the referenced component is itself a dynamic dict, use JsonElement
        ref_schema = components.get(ref_name, {})
        if _is_dynamic_dict(ref_schema):
            return 'JsonElement?'
        # Map component schema names to our generated model names
        if ref_name in known_models:
            return ref_name + "?"
        # For Resp_ prefixed models, use them directly
        return sanitize_name(pascal_case(ref_name)) + "?"

    schema_type = schema.get('type')
    schema_format = schema.get('format')

    if schema_type == 'integer':
        if schema_format == 'int64':
            return 'long?'
        return 'int?'
    elif schema_type == 'number':
        if schema_format == 'float':
            return 'float?'
        return 'double?'
    elif schema_type == 'boolean':
        return 'bool?'
    elif schema_type == 'string':
        return 'string?'
    elif schema_type == 'array':
        items = schema.get('items', {})
        # If the array items are a dynamic-dict object, the PHP API may
        # serialize numeric-keyed arrays as either JSON objects or JSON
        # arrays unpredictably — use JsonElement? for the whole field.
        if _is_dynamic_dict(items):
            return 'JsonElement?'
        item_type = openapi_type_to_csharp(items, components, known_models)
        # Strip nullable from inner type for List
        inner = item_type.rstrip('?')
        if not inner:
            inner = "JsonElement"
        return f'List<{inner}>?'
    elif schema_type == 'object':
        # Dynamic dict detection: all-numeric keys → PHP array serialised as
        # JSON object OR JSON array unpredictably; use JsonElement? for safety.
        if _is_dynamic_dict(schema):
            return 'JsonElement?'
        # If it has properties, it'll be generated as an inline model or JsonElement
        if schema.get('properties'):
            return 'JsonElement?'  # Complex inline objects -> JsonElement
        return 'JsonElement?'
    else:
        # oneOf, anyOf, allOf, or no type
        return 'JsonElement?'


def param_type_to_csharp(schema: dict, enum_registry: dict = None) -> str:
    """Convert parameter schema to C# type for method parameters."""
    if not schema:
        return "string?"
    
    # Check if this schema has enum values that match a known enum type
    if enum_registry and schema.get('enum'):
        key = frozenset(str(v) for v in schema['enum'])
        if key in enum_registry:
            return enum_registry[key] + '?'
    
    schema_type = schema.get('type')
    schema_format = schema.get('format')
    
    if schema_type == 'integer':
        if schema_format == 'int64':
            return 'long?'
        return 'int?'
    elif schema_type == 'number':
        return 'double?'
    elif schema_type == 'boolean':
        return 'bool?'
    elif schema_type == 'string':
        return 'string?'
    elif schema_type == 'array':
        items = schema.get('items', {})
        inner = param_type_to_csharp(items, enum_registry).rstrip('?') or 'string'
        return f'List<{inner}>?'
    else:
        return 'string?'


# ─── Schema Analysis ─────────────────────────────────────────────────────────

def collect_component_models(spec: dict) -> dict:
    """Extract component schemas that have properties (are real models).
    Schemas whose top-level properties are ALL numeric keys are dynamic
    dicts and should NOT be emitted as model classes."""
    models = {}
    schemas = spec.get('components', {}).get('schemas', {})
    for name, schema in schemas.items():
        props = schema.get('properties', {})
        if props:
            # Skip dynamic dicts — they'll be mapped to Dictionary/JsonElement
            if _is_dynamic_dict(schema):
                continue
            models[name] = schema
    return models


def collect_inline_response_models(spec: dict, components: dict) -> dict:
    """Extract inline response schemas that aren't just refs to components."""
    models = {}
    for path, methods in spec.get('paths', {}).items():
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            op_id = op.get('operationId', '')
            if not op_id:
                continue
            
            resp_200 = op.get('responses', {}).get('200', {})
            content = resp_200.get('content', {}).get('application/json', {})
            schema = content.get('schema', {})
            
            if not schema:
                continue
            
            # Skip pure $ref responses — they'll use component models directly
            if schema.get('$ref'):
                continue
            
            if schema.get('properties'):
                # Skip schemas that are entirely dynamic dicts
                if _is_dynamic_dict(schema):
                    continue
                class_name = model_class_name(op_id, method)
                models[class_name] = {
                    'schema': schema,
                    'operation_id': op_id,
                }
    return models


def collect_operations(spec: dict) -> dict:
    """Group operations by tag."""
    by_tag = defaultdict(list)
    
    for path, methods in spec.get('paths', {}).items():
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            op_id = op.get('operationId', '')
            if not op_id:
                continue
            
            tags = op.get('tags', ['Default'])
            tag = tags[0] if tags else 'Default'
            
            # Gather path parameters from the path string
            path_params = re.findall(r'\{(\w+)\}', path)
            
            # Gather explicit parameters
            params = []
            for p in op.get('parameters', []):
                if not isinstance(p, dict):
                    continue
                name = p.get('name')
                if not name:
                    continue
                params.append({
                    'name': name,
                    'in': p.get('in', 'query'),
                    'required': p.get('required', False),
                    'schema': p.get('schema', {}),
                    'description': p.get('description', ''),
                })
            
            # Ensure path params are in the params list
            existing_param_names = {p['name'] for p in params}
            for pp in path_params:
                if pp not in existing_param_names:
                    params.append({
                        'name': pp,
                        'in': 'path',
                        'required': True,
                        'schema': {'type': 'integer'},
                        'description': '',
                    })
            
            # Request body — detect multipart/form-data vs application/json
            request_body = None
            is_multipart = False
            is_array_body = False
            multipart_binary_fields = []  # list of field names with format: binary
            rb = op.get('requestBody', {})
            if rb:
                rb_content = rb.get('content', {})
                if 'multipart/form-data' in rb_content:
                    is_multipart = True
                    mp_schema = rb_content['multipart/form-data'].get('schema', {})
                    # Handle oneOf by merging all properties (union of all variants)
                    if mp_schema.get('oneOf'):
                        merged_props = {}
                        merged_required = set()
                        for variant in mp_schema['oneOf']:
                            for pname, pschema in variant.get('properties', {}).items():
                                if pname not in merged_props:
                                    merged_props[pname] = pschema
                            # Only mark as required if required in ALL variants
                            # For the union approach, treat nothing as strictly required
                        request_body = {'properties': merged_props, 'required': []}
                    elif mp_schema.get('properties'):
                        request_body = mp_schema
                    # Detect binary fields
                    if request_body:
                        for pname, pschema in request_body.get('properties', {}).items():
                            if pschema.get('format') == 'binary':
                                multipart_binary_fields.append(pname)
                else:
                    rb_content_json = rb_content.get('application/json', {})
                    rb_schema = rb_content_json.get('schema', {})
                    if rb_schema:
                        # Check if body schema is an array (e.g. batch endpoints)
                        if rb_schema.get('type') == 'array':
                            is_array_body = True
                        elif rb_schema.get('oneOf') or rb_schema.get('anyOf'):
                            # Flatten oneOf/anyOf variants into a single set of optional properties
                            merged_props = {}
                            for variant in rb_schema.get('oneOf', []) + rb_schema.get('anyOf', []):
                                for pname, pschema in variant.get('properties', {}).items():
                                    if pname not in merged_props:
                                        merged_props[pname] = pschema
                            if merged_props:
                                request_body = {'properties': merged_props, 'required': []}
                        elif rb_schema.get('properties'):
                            request_body = rb_schema
            
            # Response model
            resp_200 = op.get('responses', {}).get('200', {})
            resp_200_content = resp_200.get('content', {})
            # Detect text/html responses
            response_is_text = 'text/html' in resp_200_content and 'application/json' not in resp_200_content
            resp_content = resp_200_content.get('application/json', {})
            resp_schema = resp_content.get('schema', {})
            
            response_type = None
            if not response_is_text and resp_schema:
                if resp_schema.get('$ref'):
                    ref_name = resp_schema['$ref'].split('/')[-1]
                    # If the referenced component is a dynamic dict, don't
                    # use a typed model — fall back to JsonElement.
                    ref_schema = spec.get('components', {}).get('schemas', {}).get(ref_name, {})
                    if _is_dynamic_dict(ref_schema):
                        response_type = None  # will become SaveChangesResponse / JsonElement
                    else:
                        response_type = sanitize_name(pascal_case(ref_name))
                elif resp_schema.get('properties'):
                    # Skip dynamic-dict response schemas
                    if not _is_dynamic_dict(resp_schema):
                        response_type = model_class_name(op_id, method)
            
            # Fallback: endpoints with no response schema use SaveChangesResponse
            if response_type is None and not response_is_text:
                response_type = 'SaveChangesResponse'
            
            by_tag[tag].append({
                'operation_id': op_id,
                'method': method.upper(),
                'path': path,
                'path_params': path_params,
                'params': params,
                'request_body': request_body,
                'response_type': response_type,
                'summary': op.get('summary', ''),
                'description': op.get('description', ''),
                'is_multipart': is_multipart,
                'multipart_binary_fields': multipart_binary_fields,
                'is_array_body': is_array_body,
                'response_is_text': response_is_text,
            })
    
    return dict(by_tag)


# ─── Code Generation ─────────────────────────────────────────────────────────

# API type mismatch overrides — real API returns different types than spec
# Fields whose spec type doesn't match the real API.
# JsonElement? = any dynamic value; Dictionary<string, JsonElement>? = dynamic dict.
FIELD_TYPE_OVERRIDES = {
    # float / double mismatches
    'priceWithSellerFee': 'double?',
    'roblox_credit_balance': 'double?',
    # any / dynamic — real type differs radically from spec
    'steam_bans': 'JsonElement?',
    'guarantee': 'JsonElement?',
    'cs2PremierElo': 'JsonElement?',
    'discord_nitro_type': 'JsonElement?',
    'instagram_id': 'JsonElement?',
    'socialclub_games': 'JsonElement?',
    'base_params': 'JsonElement?',
    # dict or list — PHP API serialises these unpredictably
    'thread_tags': 'JsonElement?',
    'Skin': 'JsonElement?',
    'WeaponSkins': 'JsonElement?',
    'supercellBrawlers': 'JsonElement?',
    'r6Skins': 'JsonElement?',
    'tags': 'JsonElement?',
    'values': 'JsonElement?',
    # already handled, kept for completeness
    'feedback_data': 'JsonElement?',
    'imap_data': 'JsonElement?',
    'restore_data': 'JsonElement?',
    'telegram_client': 'JsonElement?',
    'backgrounds': 'JsonElement?',
    'steam_full_games': 'JsonElement?',
    # IDs and timestamps that can exceed int32 range
    'notification_id': 'long?',
    'notification_create_date': 'long?',
    'log_id': 'long?',
    # PHP can return bool(false) or int for these fields
    'autoBuyPrice': 'JsonElement?',
}

# Fields containing '_id' suffix with integer type should be long? in response models
# to handle IDs that exceed int32 range (e.g. notification_id > 2^31).
ID_SUFFIX_LONG_FIELDS = True  # Enable long? for *_id integer fields in response models

def generate_model_file(class_name: str, schema: dict, namespace: str, components: dict, known_models: set) -> str:
    """Generate a C# record class for a response model."""
    lines = [
        "// <auto-generated/>",
        "#nullable enable",
        "",
        "using System.Text.Json;",
        "using System.Text.Json.Serialization;",
        "",
        f"namespace {namespace}.Models;",
        "",
        f"/// <summary>",
        f"/// Response model: {class_name}",
        f"/// </summary>",
        f"public sealed record {class_name}",
        "{",
    ]
    
    properties = schema.get('properties', {})
    for prop_name, prop_schema in properties.items():
        if prop_name in FIELD_TYPE_OVERRIDES:
            csharp_type = FIELD_TYPE_OVERRIDES[prop_name]
        else:
            csharp_type = openapi_type_to_csharp(prop_schema, components, known_models)
        csharp_prop_name = sanitize_name(pascal_case(prop_name))
        
        desc = prop_schema.get('description', prop_schema.get('title', ''))
        if desc:
            lines.append(f"    /// <summary>{escape_xml(desc)}</summary>")
        
        lines.append(f'    [JsonPropertyName("{prop_name}")]')
        lines.append(f"    public {csharp_type} {escape_identifier(csharp_prop_name)} {{ get; init; }}")
        lines.append("")
    
    # Capture any extra/unknown JSON properties so that unknown keys (and
    # the PHP API's habit of returning [] instead of null/{}) don't cause
    # deserialization failures.
    lines.append("    /// <summary>Catches any extra properties not mapped above.</summary>")
    lines.append("    [JsonExtensionData]")
    lines.append("    public Dictionary<string, JsonElement>? ExtensionData { get; init; }")
    lines.append("")
    
    lines.append("}")
    lines.append("")
    return '\n'.join(lines)


def escape_xml(s: str) -> str:
    """Escape special characters for XML doc comments and collapse to single line."""
    # Collapse newlines to space for single-line XML summary
    s = ' '.join(s.split())
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def generate_enum_file(enum_name: str, values: list, base_type: str, namespace: str) -> str:
    """Generate a C# string-backed enum with JsonConverter."""
    lines = [
        "// <auto-generated/>",
        "#nullable enable",
        "",
        "using System.Text.Json;",
        "using System.Text.Json.Serialization;",
        "",
        f"namespace {namespace}.Enums;",
        "",
    ]
    
    if base_type == 'string':
        # String enum with JsonConverter
        lines.extend([
            f"/// <summary>String-backed enum: {enum_name}</summary>",
            f"[JsonConverter(typeof({enum_name}Converter))]",
            f"public enum {enum_name}",
            "{",
        ])
        for val in values:
            member_name = sanitize_name(pascal_case(str(val)))
            if not member_name:
                member_name = f"Value_{val}"
            lines.append(f"    /// <summary>{escape_xml(str(val))}</summary>")
            lines.append(f"    {member_name},")
            lines.append("")
        lines.append("}")
        lines.append("")
        
        # JsonConverter
        lines.extend([
            f"/// <summary>JSON converter for {enum_name}.</summary>",
            f"public sealed class {enum_name}Converter : JsonConverter<{enum_name}>",
            "{",
            f"    private static readonly Dictionary<string, {enum_name}> s_fromString = new(StringComparer.OrdinalIgnoreCase)",
            "    {",
        ])
        for val in values:
            member_name = sanitize_name(pascal_case(str(val)))
            if not member_name:
                member_name = f"Value_{val}"
            lines.append(f'        {{ "{val}", {enum_name}.{member_name} }},')
        lines.extend([
            "    };",
            "",
            f"    private static readonly Dictionary<{enum_name}, string> s_toString = new()",
            "    {",
        ])
        for val in values:
            member_name = sanitize_name(pascal_case(str(val)))
            if not member_name:
                member_name = f"Value_{val}"
            lines.append(f'        {{ {enum_name}.{member_name}, "{val}" }},')
        lines.extend([
            "    };",
            "",
            f"    public override {enum_name} Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)",
            "    {",
            "        var value = reader.GetString();",
            "        if (value != null && s_fromString.TryGetValue(value, out var result))",
            "            return result;",
            f"        throw new JsonException($\"Unknown {enum_name} value: {{value}}\");",
            "    }",
            "",
            f"    public override void Write(Utf8JsonWriter writer, {enum_name} value, JsonSerializerOptions options)",
            "    {",
            "        if (s_toString.TryGetValue(value, out var str))",
            "            writer.WriteStringValue(str);",
            "        else",
            "            writer.WriteStringValue(value.ToString());",
            "    }",
            "}",
            "",
        ])
    else:
        # Integer enum - simpler
        lines.extend([
            f"/// <summary>Integer-backed enum: {enum_name}</summary>",
            f"public enum {enum_name}",
            "{",
        ])
        for val in values:
            member_name = f"Value{val}" if isinstance(val, int) and val >= 0 else f"ValueNeg{abs(val)}" if isinstance(val, int) else sanitize_name(str(val))
            lines.append(f"    /// <summary>Value: {val}</summary>")
            lines.append(f"    {member_name} = {val},")
            lines.append("")
        lines.append("}")
        lines.append("")
    
    return lines


def generate_service_file(
    tag: str,
    operations: list,
    namespace: str,
    components: dict,
    known_models: set,
    enum_registry: dict,
) -> str:
    """Generate a service class with methods for a tag group."""
    class_name = tag_to_class_name(tag)
    
    lines = [
        "// <auto-generated/>",
        "#nullable enable",
        "",
        "using System.Text.Json;",
        "using Lolzteam.Runtime;",
        f"using {namespace}.Enums;",
        f"using {namespace}.Models;",
        "",
        f"namespace {namespace};",
        "",
        f"/// <summary>",
        f"/// API methods for: {escape_xml(tag)}",
        f"/// </summary>",
        f"public sealed class {class_name}",
        "{",
        f"    private readonly ILolzteamHttpClient _client;",
        "",
        f"    public {class_name}(ILolzteamHttpClient client)",
        "    {",
        "        _client = client ?? throw new ArgumentNullException(nameof(client));",
        "    }",
        "",
    ]
    
    # Track method names to avoid duplicates
    used_method_names = set()
    
    for op in operations:
        method_name = operation_to_method_name(op['operation_id'])
        # Deduplicate
        original = method_name
        counter = 2
        while method_name in used_method_names:
            method_name = f"{original}{counter}"
            counter += 1
        used_method_names.add(method_name)
        
        # Build parameter list
        method_params = []
        path_param_assignments = []
        query_param_assignments = []
        body_param_assignments = []
        
        # Path parameters first (required)
        for pp_name in op['path_params']:
            param_info = next((p for p in op['params'] if p['name'] == pp_name), None)
            schema = param_info['schema'] if param_info else {'type': 'integer'}
            csharp_type = param_type_to_csharp(schema, enum_registry).rstrip('?')  # Path params non-nullable
            safe_name = safe_param_name(pp_name)
            method_params.append((csharp_type, safe_name, True, pp_name))
            path_param_assignments.append((pp_name, safe_name))
        
        # Query parameters (optional ones last)
        query_params_sorted = []
        for p in op['params']:
            if p['in'] == 'path':
                continue
            if p['in'] == 'query':
                query_params_sorted.append(p)
        
        # Required first, optional last
        query_params_sorted.sort(key=lambda x: (not x['required'], x['name']))
        
        for p in query_params_sorted:
            csharp_type = param_type_to_csharp(p['schema'], enum_registry)
            safe_name = safe_param_name(p['name'])
            required = p['required']
            if required:
                csharp_type = csharp_type.rstrip('?')
            method_params.append((csharp_type, safe_name, required, p['name']))
            query_param_assignments.append((p['name'], safe_name, csharp_type, required))
        
        # Request body parameters
        is_multipart = op.get('is_multipart', False)
        multipart_binary_fields = set(op.get('multipart_binary_fields', []))
        
        if op['request_body']:
            rb_props = op['request_body'].get('properties', {})
            rb_required = set(op['request_body'].get('required', []))
            
            # Sort: required first
            sorted_props = sorted(rb_props.items(), key=lambda x: (x[0] not in rb_required, x[0]))
            
            for prop_name, prop_schema in sorted_props:
                if is_multipart and prop_name in multipart_binary_fields:
                    csharp_type = 'byte[]?'
                    safe_name = safe_param_name(prop_name)
                    required = prop_name in rb_required
                    if required:
                        csharp_type = 'byte[]'
                else:
                    csharp_type = param_type_to_csharp(prop_schema, enum_registry)
                    safe_name = safe_param_name(prop_name)
                    required = prop_name in rb_required
                    if required:
                        csharp_type = csharp_type.rstrip('?')
                # Avoid collision with path params
                if safe_name in {p[1] for p in method_params}:
                    safe_name = 'body' + pascal_case(safe_name)
                method_params.append((csharp_type, safe_name, required, prop_name))
                body_param_assignments.append((prop_name, safe_name, csharp_type))
        
        # For array body schemas (e.g. batch), add a jobs parameter
        is_array_body = op.get('is_array_body', False)
        response_is_text = op.get('response_is_text', False)
        if is_array_body:
            # Insert jobs parameter before CancellationToken
            method_params.append(('List<Dictionary<string, object?>>', 'jobs', True, None))

        # CancellationToken always last
        method_params.append(('CancellationToken', 'cancellationToken', False, None))
        
        # Return type
        if response_is_text:
            return_type = 'string'
            async_return = 'Task<string>'
        else:
            return_type = op['response_type'] or 'JsonElement'
            if return_type == 'JsonElement':
                async_return = 'Task<JsonElement>'
            else:
                async_return = f'Task<{return_type}?>'
        
        # Build method signature
        desc = op.get('description') or op.get('summary') or f"{op['method']} {op['path']}"
        lines.append(f"    /// <summary>{escape_xml(desc)}</summary>")
        
        sig_parts = []
        for ctype, cname, required, _ in method_params:
            if cname == 'cancellationToken':
                sig_parts.append(f"CancellationToken cancellationToken = default")
            elif not required and '?' not in ctype:
                sig_parts.append(f"{ctype}? {escape_identifier(cname)} = null")
            elif not required:
                sig_parts.append(f"{ctype} {escape_identifier(cname)} = null")
            else:
                sig_parts.append(f"{ctype} {escape_identifier(cname)}")
        
        sig = ', '.join(sig_parts)
        lines.append(f"    public async {async_return} {method_name}Async({sig})")
        lines.append("    {")
        
        # Build the path with substitutions
        api_path = op['path']
        if path_param_assignments:
            path_expr = 'var path = $"' + api_path.replace('{', '{').replace('}', '}')
            # Replace {param_name} with {safeName}
            for orig_name, safe_name in path_param_assignments:
                path_expr = path_expr.replace('{' + orig_name + '}', '{' + escape_identifier(safe_name) + '}')
            path_expr += '";'
            lines.append(f"        {path_expr}")
        else:
            lines.append(f'        var path = "{api_path}";')
        
        # Query params dict
        if query_param_assignments:
            lines.append("        var queryParams = new Dictionary<string, string>();")
            for qname, qsafe, qtype, qreq in query_param_assignments:
                safe = escape_identifier(qsafe)
                if 'List<' in qtype:
                    lines.append(f"        if ({safe} != null)")
                    lines.append(f"        {{")
                    lines.append(f"            for (var i = 0; i < {safe}.Count; i++)")
                    # If the param name has [] already
                    if '[]' in qname:
                        lines.append(f'                queryParams[$"{qname.replace("[]", "")}[{{i}}]"] = {safe}[i].ToString();')
                    else:
                        lines.append(f'                queryParams[$"{qname}[{{i}}]"] = {safe}[i].ToString();')
                    lines.append(f"        }}")
                elif '?' in qtype or not qreq:
                    lines.append(f"        if ({safe} != null)")
                    if 'bool' in qtype:
                        lines.append(f'            queryParams["{qname}"] = {safe}.Value ? "1" : "0";')
                    else:
                        lines.append(f'            queryParams["{qname}"] = {safe}.ToString()!;')
                else:
                    if 'bool' in qtype:
                        lines.append(f'        queryParams["{qname}"] = {safe} ? "1" : "0";')
                    else:
                        lines.append(f'        queryParams["{qname}"] = {safe}.ToString()!;')
        else:
            lines.append("        Dictionary<string, string>? queryParams = null;")
        
        # Make the request
        http_method = op['method']
        method_map = {
            'GET': 'HttpMethod.Get',
            'POST': 'HttpMethod.Post',
            'PUT': 'HttpMethod.Put',
            'DELETE': 'HttpMethod.Delete',
            'PATCH': 'HttpMethod.Patch',
        }
        http_method_expr = method_map.get(http_method, f'new HttpMethod("{http_method}")')

        if is_multipart and body_param_assignments:
            # Build multipart form fields and file fields
            has_form_fields = any(bname not in multipart_binary_fields for bname, _, _ in body_param_assignments)
            has_file_fields = any(bname in multipart_binary_fields for bname, _, _ in body_param_assignments)

            if has_form_fields:
                lines.append("        var formFields = new Dictionary<string, string>();")
                for bname, bsafe, btype in body_param_assignments:
                    if bname in multipart_binary_fields:
                        continue
                    safe = escape_identifier(bsafe)
                    if 'List<' in btype:
                        if '?' in btype:
                            lines.append(f"        if ({safe} != null)")
                            lines.append(f'            formFields["{bname}"] = string.Join(",", {safe});')
                        else:
                            lines.append(f'        formFields["{bname}"] = string.Join(",", {safe});')
                    elif '?' in btype:
                        lines.append(f"        if ({safe} != null)")
                        lines.append(f'            formFields["{bname}"] = {safe}.ToString()!;')
                    else:
                        lines.append(f'        formFields["{bname}"] = {safe}.ToString()!;')
            else:
                lines.append("        Dictionary<string, string>? formFields = null;")

            if has_file_fields:
                lines.append("        var fileFields = new Dictionary<string, (string FileName, byte[] Content)>();")
                for bname, bsafe, btype in body_param_assignments:
                    if bname not in multipart_binary_fields:
                        continue
                    safe = escape_identifier(bsafe)
                    if '?' in btype:
                        lines.append(f"        if ({safe} != null)")
                        lines.append(f'            fileFields["{bname}"] = ("{bname}", {safe});')
                    else:
                        lines.append(f'        fileFields["{bname}"] = ("{bname}", {safe});')
            else:
                lines.append("        Dictionary<string, (string FileName, byte[] Content)>? fileFields = null;")

            lines.append(f"        var response = await _client.RequestMultipartAsync({http_method_expr}, path, queryParams, formFields, fileFields, cancellationToken).ConfigureAwait(false);")
        elif is_array_body:
            # Array body (e.g. batch endpoints) — pass list directly as body
            lines.append(f"        var response = await _client.RequestAsync({http_method_expr}, path, queryParams, jobs, cancellationToken).ConfigureAwait(false);")
        else:
            # Normal JSON body
            if body_param_assignments:
                lines.append("        var body = new Dictionary<string, object?>")
                lines.append("        {")
                for bname, bsafe, btype in body_param_assignments:
                    lines.append(f'            {{ "{bname}", {escape_identifier(bsafe)} }},')
                lines.append("        };")
                body_var = "body"
            else:
                body_var = "null"

            lines.append(f"        var response = await _client.RequestAsync({http_method_expr}, path, queryParams, {body_var}, cancellationToken).ConfigureAwait(false);")
        
        if response_is_text:
            lines.append('        return response.ValueKind == JsonValueKind.String ? response.GetString()! : response.GetRawText();')
        elif return_type == 'JsonElement':
            lines.append("        return response;")
        else:
            lines.append(f"        return JsonSerializer.Deserialize<{return_type}>(response.GetRawText());")

        
        lines.append("    }")
        lines.append("")
    
    lines.append("}")
    lines.append("")
    return '\n'.join(lines)


def generate_client_file(tags: list, namespace: str, client_name: str) -> str:
    """Generate the main client class that exposes service groups."""
    lines = [
        "// <auto-generated/>",
        "#nullable enable",
        "",
        "using Lolzteam.Runtime;",
        "",
        f"namespace {namespace};",
        "",
        f"/// <summary>",
        f"/// Main API client for {client_name.replace('Client', '')} API.",
        f"/// </summary>",
        f"public sealed class {client_name}",
        "{",
        f"    private readonly ILolzteamHttpClient _client;",
        "",
    ]
    
    # Properties for each service
    for tag in sorted(tags):
        service_class = tag_to_class_name(tag)
        prop_name = sanitize_name(pascal_case(tag))
        lines.append(f"    /// <summary>Methods for: {escape_xml(tag)}</summary>")
        lines.append(f"    public {service_class} {prop_name} {{ get; }}")
        lines.append("")
    
    # Constructor
    lines.append(f"    public {client_name}(ILolzteamHttpClient client)")
    lines.append("    {")
    lines.append("        _client = client ?? throw new ArgumentNullException(nameof(client));")
    for tag in sorted(tags):
        service_class = tag_to_class_name(tag)
        prop_name = sanitize_name(pascal_case(tag))
        lines.append(f"        {prop_name} = new {service_class}(client);")
    lines.append("    }")
    lines.append("")
    
    lines.append("}")
    lines.append("")
    return '\n'.join(lines)


# ─── Enum Collection ─────────────────────────────────────────────────────────

def collect_enums(spec: dict) -> dict:
    """Collect all enum definitions from params and request bodies."""
    enums = {}  # name -> (values, base_type)
    
    for path, methods in spec.get('paths', {}).items():
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            op_id = op.get('operationId', '')
            
            # From parameters
            for p in op.get('parameters', []):
                if not isinstance(p, dict):
                    continue
                schema = p.get('schema', {})
                if schema.get('enum'):
                    pname = p.get('name', 'Unknown')
                    enum_name = sanitize_name(pascal_case(pname)) + "Enum"
                    values = schema['enum']
                    base_type = schema.get('type', 'string')
                    key = (tuple(sorted(str(v) for v in values)), base_type)
                    if key not in {(tuple(sorted(str(v) for v in vs)), bt) for vs, bt in enums.values()}:
                        # Deduplicate by value set
                        enums[enum_name] = (values, base_type)
            
            # From request body
            rb = op.get('requestBody', {})
            if rb:
                rb_schema = rb.get('content', {}).get('application/json', {}).get('schema', {})
                for prop_name, prop_schema in rb_schema.get('properties', {}).items():
                    if prop_schema.get('enum'):
                        enum_name = sanitize_name(pascal_case(prop_name)) + "Enum"
                        values = prop_schema['enum']
                        base_type = prop_schema.get('type', 'string')
                        key = (tuple(sorted(str(v) for v in values)), base_type)
                        if key not in {(tuple(sorted(str(v) for v in vs)), bt) for vs, bt in enums.values()}:
                            enums[enum_name] = (values, base_type)
    
    return enums


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Generate C# API client from OpenAPI schema')
    parser.add_argument('--schema', required=True, help='Path to OpenAPI JSON schema')
    parser.add_argument('--output-dir', required=True, help='Output directory')
    parser.add_argument('--namespace', required=True, help='C# namespace')
    args = parser.parse_args()
    
    with open(args.schema) as f:
        spec = json.load(f)
    
    output_dir = args.output_dir
    namespace = args.namespace
    
    # Create directories
    models_dir = os.path.join(output_dir, 'Models')
    enums_dir = os.path.join(output_dir, 'Enums')
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(enums_dir, exist_ok=True)
    
    components = spec.get('components', {}).get('schemas', {})
    
    # Determine client name from the last part of namespace
    ns_last = namespace.split('.')[-1]
    client_name = ns_last + 'Client'
    
    # ── Step 1: Generate component models ──
    component_models = collect_component_models(spec)
    known_models = set(component_models.keys())
    
    # ── Step 2: Generate inline response models ──
    inline_models = collect_inline_response_models(spec, components)
    known_models.update(inline_models.keys())
    
    total_models = 0
    
    # Write component models
    for name, schema in component_models.items():
        code = generate_model_file(name, schema, namespace, components, known_models)
        filepath = os.path.join(models_dir, f'{name}.cs')
        with open(filepath, 'w') as f:
            f.write(code)
        total_models += 1
    
    # Write inline response models
    for class_name, info in inline_models.items():
        schema = info['schema']
        code = generate_model_file(class_name, schema, namespace, components, known_models)
        filepath = os.path.join(models_dir, f'{class_name}.cs')
        with open(filepath, 'w') as f:
            f.write(code)
        total_models += 1
    
    # Write SaveChangesResponse fallback model for endpoints with no response schema.
    # The API always returns {"status": "ok", "message": "...", "system_info": {...}}
    save_changes_schema = {
        'properties': {
            'status': {'type': 'string', 'description': 'Status of the operation'},
            'message': {'type': 'string', 'description': 'Response message'},
            'system_info': {'$ref': '#/components/schemas/Resp_SystemInfo'},
        }
    }
    code = generate_model_file('SaveChangesResponse', save_changes_schema, namespace, components, known_models)
    filepath = os.path.join(models_dir, 'SaveChangesResponse.cs')
    with open(filepath, 'w') as f:
        f.write(code)
    total_models += 1
    known_models.add('SaveChangesResponse')
    
    # ── Step 3: Generate enums ──
    enums = collect_enums(spec)
    total_enums = 0
    
    for enum_name, (values, base_type) in enums.items():
        if base_type == 'string':
            code_lines = generate_enum_file(enum_name, values, base_type, namespace)
            code = '\n'.join(code_lines)
            filepath = os.path.join(enums_dir, f'{enum_name}.cs')
            with open(filepath, 'w') as f:
                f.write(code)
            total_enums += 1
        # For integer enums, we just use int? in params (simpler)
    
    # ── Step 4: Generate service classes ──
    operations_by_tag = collect_operations(spec)
    tags = list(operations_by_tag.keys())
    total_services = 0
    
    # Build enum registry: maps (param_name, frozenset(values)) -> enum_class_name
    # and also a simpler values_to_enum lookup
    enum_registry = {}  # frozenset(str(v) for v in values) -> enum_name
    for enum_name, (values, base_type) in enums.items():
        if base_type == 'string':
            key = frozenset(str(v) for v in values)
            enum_registry[key] = enum_name
    
    for tag, ops in operations_by_tag.items():
        code = generate_service_file(tag, ops, namespace, components, known_models, enum_registry)
        class_name = tag_to_class_name(tag)
        filepath = os.path.join(output_dir, f'{class_name}.cs')
        with open(filepath, 'w') as f:
            f.write(code)
        total_services += 1
    
    # ── Step 5: Generate main client class ──
    client_code = generate_client_file(tags, namespace, client_name)
    filepath = os.path.join(output_dir, f'{client_name}.cs')
    with open(filepath, 'w') as f:
        f.write(client_code)
    
    print(f"Generated for {namespace}:")
    print(f"  {total_models} models in {models_dir}")
    print(f"  {total_enums} enums in {enums_dir}")
    print(f"  {total_services} service classes")
    print(f"  1 client class: {client_name}")


if __name__ == '__main__':
    main()
