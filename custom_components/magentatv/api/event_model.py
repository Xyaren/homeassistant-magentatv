from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventModel(BaseModel):
    """Pydantic baseclass with overloaded operator for
    instantiating new objects.
    """

    model_config = ConfigDict(populate_by_name=False, frozen=True)

    def set_keys(self):
        return self.model_dump(exclude_unset=True, by_alias=False).keys()


class PlayContentEvent(EventModel):
    new_play_mode: int | None = None
    play_back_state: int | None = Field(alias="playBackState", default=None)
    media_type: int | None = Field(alias="mediaType", default=None)
    media_code: str | None = Field(alias="mediaCode", default=None)
    duration: int | None = None
    play_position: int | None = Field(alias="playPostion", default=None)  # not a typo !
    fast_speed: int | None = Field(alias="fastSpeed", default=None)
    chan_key: int | None = Field(alias="chanKey", default=None)


class ShortEvent(EventModel):
    language_code: str
    event_name: str
    text_char: str


class ProgramInfo(EventModel):
    event_id: str
    start_time: str
    duration: str
    running_status: int
    free_ca_mode: bool = Field(False, alias="free_CA_mode")
    short_event: list[ShortEvent]


class EitChangedEvent(EventModel):
    type: str
    instance_id: int
    channel_code: int
    channel_num: int | None
    media_id: str = Field(alias="mediaId")
    program_info: list[ProgramInfo | None]

    @field_validator("program_info", mode="before")
    @classmethod
    def filter_empty_program_info(cls, value) -> list[ProgramInfo | None]:
        return [x if x else None for x in value]
