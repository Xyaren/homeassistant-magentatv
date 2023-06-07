from typing import List
from pydantic import BaseModel, Field


def _to_camel(string: str) -> str:
    result = "".join(word.capitalize() for word in string.split("_"))
    result = result[0].lower() + result[1:]
    return result


class EventModel(BaseModel):
    """
    Pydantic baseclass with overloaded operator for
    instantiating new objects.
    """

    def __new__(cls, *args, **kwargs):
        """Be careful when using this method:
        https://docs.python.org/3/reference/datamodel.html#object.__new__
        """
        # If all args are none -> do nothing
        if all(v is None for v in args) and all(v is None for v in kwargs.values()):
            pass
        else:
            return super().__new__(cls)

    class Config:
        allow_population_by_field_name = True
        # alias_generator = _to_camel
        allow_mutation = False


class PlayContentEvent(EventModel):
    new_play_mode: int | None
    play_back_state: int | None = Field(alias="playBackState")
    media_type: int | None = Field(alias="mediaType")
    media_code: str | None = Field(alias="mediaCode")
    duration: int | None
    play_position: int | None = Field(alias="playPostion")  # not a typo !


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
    short_event: List[ShortEvent]


class EitChangedEvent(EventModel):
    type: str
    instance_id: int
    channel_code: str
    channel_num: str
    media_id: str = Field(alias="mediaId")
    program_info: List[ProgramInfo]
