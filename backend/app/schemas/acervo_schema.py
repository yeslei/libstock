from pydantic import BaseModel, ConfigDict, Field, model_validator


class DestinationTagResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ClassifyItemInput(BaseModel):
    tag_id: int | None = Field(default=None, description="ID numérico da tag de destinação")
    tag_name: str | None = Field(default=None, description="Nome ou slug da tag de destinação")

    @model_validator(mode="after")
    def validate_tag_provided(self) -> "ClassifyItemInput":
        if self.tag_id is None and (not self.tag_name or not self.tag_name.strip()):
            raise ValueError("É necessário informar 'tag_id' ou 'tag_name' para classificar o item.")
        if self.tag_name is not None:
            self.tag_name = self.tag_name.strip()
        return self


class AcervoItemResponse(BaseModel):
    id: int
    book_id: int
    barcode: str
    status: str
    destination: str
    destination_tag: DestinationTagResponse | None = None

    model_config = ConfigDict(from_attributes=True)

