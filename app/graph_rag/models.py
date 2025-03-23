from pydantic import Field
from pydantic import BaseModel


class UserQuery(BaseModel):
    query: str = Field(description="The user's original query, optionally including information from another tool.")
    lang: str = Field(description="The user query language in ISO 639 format, e.g., id, en")


class VisualizeQuery(BaseModel):
    query: str = Field(description="The user's original query, as is (don't change it).")
    answer: str = Field(description="The answer to user original query from other tools")
    lang: str = Field(description="The user query language in ISO 639 format, e.g., id, en")
