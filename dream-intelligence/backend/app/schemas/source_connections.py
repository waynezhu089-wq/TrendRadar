"""Declarative, bounded source definitions; credentials are environment references only."""
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.research.websites import normalize_site_url


def public_endpoint(value: str) -> str:
    if urlsplit(value).query or urlsplit(value).fragment:
        raise ValueError('Parameters must be configured separately')
    value = normalize_site_url(value)
    parts = urlsplit(value)
    if parts.scheme != 'https' or parts.query or parts.fragment:
        raise ValueError('Use a public HTTPS URL without query parameters or credentials')
    return value


def field_path(value: str) -> str:
    if value and not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*', value):
        raise ValueError('Use dotted JSON field names only')
    return value


class SourceDefinition(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    site_url: str
    adapter: Literal['json_api', 'rss'] = 'json_api'
    endpoint: str
    description: str = Field(default='', max_length=400)
    enabled: bool = True
    auth_env: str = Field(default='', max_length=80)
    auth_required: bool = False
    query_param: str = Field(default='q', max_length=40)
    query_suffix: str = Field(default='', max_length=80)
    items_path: str = Field(default='items', max_length=100)
    field_map: dict[str, str] = Field(default_factory=lambda: {
        'id': 'id', 'title': 'title', 'url': 'url', 'content': 'description'})
    url_prefix: str = ''
    params: dict[str, str] = Field(default_factory=dict, max_length=12)
    sort_param: str = Field(default='sort', max_length=40)
    sort_values: list[str] = Field(default_factory=list, max_length=8)
    default_sort: str = Field(default='', max_length=40)
    limit_param: str = Field(default='limit', max_length=40)
    max_results: int = Field(default=12, ge=1, le=12, strict=True)

    @field_validator('site_url', 'endpoint')
    @classmethod
    def clean_url(cls, value):
        return public_endpoint(value)

    @field_validator('url_prefix')
    @classmethod
    def clean_prefix(cls, value):
        return public_endpoint(value) if value else ''

    @field_validator('auth_env')
    @classmethod
    def credential_reference(cls, value):
        if value and not re.fullmatch(r'GITHUB_TOKEN|DSIH_SOURCE_[A-Z][A-Z0-9_]{0,62}', value):
            raise ValueError('Use GITHUB_TOKEN or a DSIH_SOURCE_* environment variable name')
        return value

    @field_validator('field_map')
    @classmethod
    def clean_map(cls, values):
        if not {'id', 'title'} <= values.keys() or not values.get('id') or not values.get('title'):
            raise ValueError('ID and title mappings are required')
        if values.keys() - {'id', 'title', 'url', 'content', 'published_at', 'stars', 'updated_at'}:
            raise ValueError('Unsupported output field')
        return {key: field_path(value) for key, value in values.items()}

    @model_validator(mode='after')
    def bounded_configuration(self):
        field_path(self.items_path)
        reserved = re.compile(r'(^key$|token|secret|password|cookie|authorization|credential|api.?key|access.?key)', re.I)
        for key in [self.query_param, self.sort_param, self.limit_param, *self.params]:
            if key and (not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,39}', key) or reserved.search(key)):
                raise ValueError('Credentials cannot be query parameters')
        if any(len(value) > 256 or '\n' in value or '\r' in value for value in self.params.values()):
            raise ValueError('Invalid fixed query parameters')
        if '\n' in self.query_suffix or '\r' in self.query_suffix:
            raise ValueError('Invalid query suffix')
        dynamic = [value for value in (self.query_param, self.sort_param, self.limit_param) if value]
        if len(set(dynamic)) != len(dynamic) or set(dynamic) & self.params.keys():
            raise ValueError('Query parameter names must be distinct')
        if any(not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', value) for value in self.sort_values):
            raise ValueError('Invalid sort choices')
        if self.default_sort and self.default_sort not in self.sort_values:
            raise ValueError('Default sort must be an allowed choice')
        if self.auth_required and not self.auth_env:
            raise ValueError('Required authentication needs an environment reference')
        if self.auth_env == 'GITHUB_TOKEN' and urlsplit(self.endpoint).hostname != 'api.github.com':
            raise ValueError('GITHUB_TOKEN can only be used with api.github.com')
        if self.adapter == 'rss' and self.auth_env:
            raise ValueError('RSS currently supports public feeds only')
        if self.adapter == 'json_api' and not (self.field_map.get('url') or self.url_prefix):
            raise ValueError('Provide a URL field or public URL prefix')
        return self


class SourceBinding(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, from_attributes=True)
    connection_id: int = Field(ge=1, strict=True)
    query: str = Field(default='', max_length=256)
    sort: str = Field(default='', max_length=40)
    limit: int = Field(default=6, ge=1, le=12, strict=True)


class SourceConnectionOutput(SourceDefinition):
    id: int
    credential_present: bool
    ready: bool


class SourceBindingsInput(BaseModel):
    bindings: list[SourceBinding] = Field(max_length=5)
