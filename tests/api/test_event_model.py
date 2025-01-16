
from pydantic import TypeAdapter

from custom_components.magentatv.api import EitChangedEvent, PlayContentEvent


def test_play_content_event_event_deserializes():
    data = '{"new_play_mode":0,"playBackState":1,"mediaType":1,"mediaCode":"3665"}'
    ta = TypeAdapter(PlayContentEvent)
    obj = ta.validate_json(data)
    assert obj.model_dump() == {
        "chan_key": None,
        "duration": None,
        "fast_speed": None,
        "media_code": "3665",
        "media_type": 1,
        "new_play_mode": 0,
        "play_back_state": 1,
        "play_position": None,
    }
    assert True


def test_eit_change_event_deserializes():
    data = '{"type":"EVENT_EIT_CHANGE","instance_id":23,"channel_code":"391","channel_num":"4","mediaId":"3713","program_info":[{"event_id":"31788","start_time":"2023/05/29 09:30:00","duration":"01:40:00","running_status":4,"free_CA_mode":false,"short_event":[{"language_code":"DEU","event_name":"Ich glaub\' mich knutscht ein Elch!","text_char":""}]},{"event_id":"31789","start_time":"2023/05/29 11:10:00","duration":"01:35:00","running_status":1,"free_CA_mode":false,"short_event":[{"language_code":"DEU","event_name":"Ghostbusters - Die Geisterjäger","text_char":""}]}]}'
    ta = TypeAdapter(EitChangedEvent)
    obj = ta.validate_json(data)
    assert obj.model_dump() == {
        "type": "EVENT_EIT_CHANGE",
        "instance_id": 23,
        "channel_code": 391,
        "channel_num": 4,
        "media_id": "3713",
        "program_info": [
            {
                "event_id": "31788",
                "start_time": "2023/05/29 09:30:00",
                "duration": "01:40:00",
                "running_status": 4,
                "free_ca_mode": False,
                "short_event": [
                    {
                        "language_code": "DEU",
                        "event_name": "Ich glaub' mich knutscht ein Elch!",
                        "text_char": "",
                    }
                ],
            },
            {
                "event_id": "31789",
                "start_time": "2023/05/29 11:10:00",
                "duration": "01:35:00",
                "running_status": 1,
                "free_ca_mode": False,
                "short_event": [
                    {
                        "language_code": "DEU",
                        "event_name": "Ghostbusters - Die Geisterjäger",
                        "text_char": "",
                    }
                ],
            },
        ],
    }
    assert True


def test_eit_change_event_empty_deserializes():
    data = '{"type":"EVENT_EIT_CHANGE","instance_id":23,"channel_code":"378","channel_num":"5","mediaId":"3710","program_info":[{},{}]}'
    ta = TypeAdapter(EitChangedEvent)
    obj = ta.validate_json(data)
    assert obj.model_dump() == {
        "type": "EVENT_EIT_CHANGE",
        "instance_id": 23,
        "channel_code": 378,
        "channel_num": 5,
        "media_id": "3710",
        "program_info": [None, None],
    }
    assert True
