from custom_components.magentatv.api import MediaReceiverStateMachine, State


def assert_unknwon(sm: MediaReceiverStateMachine):
    assert sm.state is None
    assert_non_state_attributes_none(sm)


def assert_off(sm: MediaReceiverStateMachine):
    assert sm.state == State.OFF
    assert_non_state_attributes_none(sm)


def assert_non_state_attributes_none(sm: MediaReceiverStateMachine):
    assert sm.chanKey is None
    assert sm.duration is None
    assert sm.position is None
    assert sm.program_current is None
    assert sm.program_next is None


def test_state_machine_empty():
    sm = MediaReceiverStateMachine()
    assert_unknwon(sm)


def test_state_machine_deep_sleep():
    sm = MediaReceiverStateMachine()
    for _ in range(4):
        sm.on_poll_player_state({"playBackState": "0"})
        assert_off(sm)


def test_state_machine_shallow_sleep():
    """When turning the MR on and off this is happening."""
    # turn on MR
    # turn off MR

    # start HA
    sm = MediaReceiverStateMachine()
    for _ in range(4):
        sm.on_poll_player_state(
            {
                "chanKey": "5",
                "mediaCode": "3710",
                "mediaType": "1",
                "playBackState": "1",
            }
        )

        # treated as unknwon
        assert_unknwon(sm)


def test_state_machine_shallow_sleep_then_on():
    """When turning the MR on and off this is happening."""
    # turn on MR
    # turn off MR

    # start HA
    sm = MediaReceiverStateMachine()
    assert_unknwon(sm)
    sm.on_poll_player_state(
        {"chanKey": "5", "mediaCode": "3710", "mediaType": "1", "playBackState": "1"}
    )
    assert_unknwon(sm)

    # turn on MR
    for _ in range(2):
        sm.on_event_play_content(
            {
                "new_play_mode": 20,
                "playBackState": 1,
                "mediaType": 1,
                "mediaCode": "3710",
            }
        )
        assert sm.state == State.BUFFERING
        assert_non_state_attributes_none(sm)
    for _ in range(2):
        sm.on_event_eit_changed(
            {
                "type": "EVENT_EIT_CHANGE",
                "instance_id": 23,
                "channel_code": "378",
                "channel_num": "5",
                "mediaId": "3710",
                "program_info": [
                    {
                        "event_id": "16684",
                        "start_time": "2023/06/14 16:45:00",
                        "duration": "00:45:00",
                        "running_status": 4,
                        "free_CA_mode": False,
                        "short_event": [
                            {
                                "language_code": "DEU",
                                "event_name": "Lebensmitteltricks - Lege packt aus",
                                "text_char": "Süße Lebensmittelsünden",
                            }
                        ],
                    },
                    {
                        "event_id": "16685",
                        "start_time": "2023/06/14 17:30:00",
                        "duration": "00:45:00",
                        "running_status": 1,
                        "free_CA_mode": False,
                        "short_event": [
                            {
                                "language_code": "DEU",
                                "event_name": "Lebensmitteltricks - Lege packt aus",
                                "text_char": "Falsche Feinkost-Versprechen",
                            }
                        ],
                    },
                ],
            }
        )
        assert sm.state == State.BUFFERING  # eit event should not change state
        assert sm.chanKey == 5
        assert sm.duration is None
        assert sm.position is None
        assert (
            sm.program_current.short_event[0].event_name
            == "Lebensmitteltricks - Lege packt aus"
        )

    sm.on_event_play_content(
        {"new_play_mode": 4, "playBackState": 1, "mediaType": 1, "mediaCode": "3710"}
    )
    assert sm.state == State.PLAYING
    assert sm.chanKey == 5
    assert sm.duration == 0
    assert sm.position == 0
    assert (
        sm.program_current.short_event[0].event_name
        == "Lebensmitteltricks - Lege packt aus"
    )

    for _ in range(4):
        # player poll endpoint serves outdated data
        sm.on_poll_player_state(
            {
                "chanKey": "5",
                "mediaCode": "3710",
                "mediaType": "1",
                "playBackState": "1",
            }
        )
        assert sm.state == State.PLAYING  # should be ignored
        assert sm.chanKey == 5
        assert sm.duration == 0
        assert sm.position == 0
        assert (
            sm.program_current.short_event[0].event_name
            == "Lebensmitteltricks - Lege packt aus"
        )

    # MR state endpoint serves new data
    sm.on_poll_player_state(
        {
            "chanKey": "5",
            "duration": "5",
            "mediaCode": "3710",
            "mediaType": "1",
            "playBackState": "1",
            "playPostion": "5",
        }
    )
    assert sm.state == State.PLAYING  # should be ignored
    assert sm.chanKey == 5
    assert sm.duration == 5
    assert sm.position == 5
    assert (
        sm.program_current.short_event[0].event_name
        == "Lebensmitteltricks - Lege packt aus"
    )

    sm.on_poll_player_state(
        {
            "chanKey": "5",
            "duration": "15",
            "mediaCode": "3710",
            "mediaType": "1",
            "playBackState": "1",
            "playPostion": "15",
        }
    )
    assert sm.state == State.PLAYING
    assert sm.chanKey == 5
    assert sm.duration == 15
    assert sm.position == 15
    assert (
        sm.program_current.short_event[0].event_name
        == "Lebensmitteltricks - Lege packt aus"
    )

    # turn MR off
    sm.on_event_play_content(
        {"new_play_mode": 0, "playBackState": 1, "mediaType": 1, "mediaCode": "3710"}
    )
    assert sm.state == State.OFF
    assert_non_state_attributes_none(sm)

    for _ in range(4):
        sm.on_poll_player_state(
            {
                "chanKey": "5",
                "mediaCode": "3710",
                "mediaType": "1",
                "playBackState": "1",
            }
        )
        assert sm.state == State.OFF
        assert_non_state_attributes_none(sm)


def test_state_machine_shallow_sleep_then_on_without_events():
    # turn on MR
    # turn off MR

    # start HA
    sm = MediaReceiverStateMachine()
    assert_unknwon(sm)
    sm.on_poll_player_state(
        {"chanKey": "5", "mediaCode": "3710", "mediaType": "1", "playBackState": "1"}
    )
    assert_unknwon(sm)

    # turn on MR
    for _ in range(4):
        # player poll endpoint serves outdated data
        sm.on_poll_player_state(
            {
                "chanKey": "5",
                "mediaCode": "3710",
                "mediaType": "1",
                "playBackState": "1",
            }
        )
        assert_unknwon(sm)

    # MR state endpoint serves new data
    sm.on_poll_player_state(
        {
            "chanKey": "5",
            "duration": "5",
            "mediaCode": "3710",
            "mediaType": "1",
            "playBackState": "1",
            "playPostion": "5",
        }
    )
    assert sm.state == State.PLAYING
    assert sm.chanKey == 5
    assert sm.duration == 5
    assert sm.position == 5
    assert sm.program_current is None
    assert sm.program_next is None

    sm.on_poll_player_state(
        {
            "chanKey": "5",
            "duration": "15",
            "mediaCode": "3710",
            "mediaType": "1",
            "playBackState": "1",
            "playPostion": "15",
        }
    )
    # treated as unknwon
    assert sm.state == State.PLAYING
    assert sm.chanKey == 5
    assert sm.duration == 15
    assert sm.position == 15
    assert sm.program_current is None
    assert sm.program_next is None

    # turn MR off
    for _ in range(4):
        sm.on_poll_player_state(
            {
                "chanKey": "5",
                "mediaCode": "3710",
                "mediaType": "1",
                "playBackState": "1",
            }
        )
        assert sm.state == State.OFF
        assert_non_state_attributes_none(sm)


def test_on_then_channel_change():
    # start HA, MR is ON
    sm = MediaReceiverStateMachine()
    assert_unknwon(sm)
    sm.on_poll_player_state(
        {
            "chanKey": "1",
            "duration": "8",
            "mediaCode": "3479",
            "mediaType": "1",
            "playBackState": "1",
            "playPostion": "8",
        }
    )
    assert sm.state == State.PLAYING
    assert sm.chanKey == 1
    assert sm.duration == 8
    assert sm.position == 8
    assert sm.program_current is None
    assert sm.program_next is None

    sm.on_event_play_content(
        {"new_play_mode": 20, "playBackState": 1, "mediaType": 1, "mediaCode": "3479"}
    )
    assert sm.state == State.BUFFERING
    assert sm.chanKey == 1  # ?
    assert sm.duration is None
    assert sm.position is None
    assert sm.program_current is None
    assert sm.program_next is None

    sm.on_event_play_content(
        {"new_play_mode": 20, "playBackState": 1, "mediaType": 1, "mediaCode": "3733"}
    )
    assert sm.state == State.BUFFERING
    assert sm.chanKey == 1
    assert sm.duration is None
    assert sm.position is None
    assert sm.program_current is None
    assert sm.program_next is None

    sm.on_event_eit_changed(
        {
            "type": "EVENT_EIT_CHANGE",
            "instance_id": 23,
            "channel_code": "408",
            "channel_num": "2",
            "mediaId": "3733",
            "program_info": [
                {
                    "event_id": "51625",
                    "start_time": "2023/06/14 18:15:00",
                    "duration": "01:30:00",
                    "running_status": 4,
                    "free_CA_mode": False,
                    "short_event": [
                        {
                            "language_code": "DEU",
                            "event_name": "Aktenzeichen XY... Ungelöst",
                            "text_char": "Die Kriminalpolizei bittet um Mithilfe",
                        }
                    ],
                },
                {
                    "event_id": "51626",
                    "start_time": "2023/06/14 19:45:00",
                    "duration": "00:30:00",
                    "running_status": 1,
                    "free_CA_mode": False,
                    "short_event": [
                        {
                            "language_code": "DEU",
                            "event_name": "heute journal",
                            "text_char": "Wetter",
                        }
                    ],
                },
            ],
        }
    )
    assert sm.state == State.BUFFERING
    assert sm.chanKey == 2
    assert sm.duration is None
    assert sm.position is None
    assert sm.program_current.short_event[0].event_name == "Aktenzeichen XY... Ungelöst"

    sm.on_event_eit_changed(
        {
            "type": "EVENT_EIT_CHANGE",
            "instance_id": 23,
            "channel_code": "408",
            "channel_num": "2",
            "mediaId": "3733",
            "program_info": [
                {
                    "event_id": "51625",
                    "start_time": "2023/06/14 18:15:00",
                    "duration": "01:30:00",
                    "running_status": 4,
                    "free_CA_mode": False,
                    "short_event": [
                        {
                            "language_code": "DEU",
                            "event_name": "Aktenzeichen XY... Ungelöst",
                            "text_char": "Die Kriminalpolizei bittet um Mithilfe",
                        }
                    ],
                },
                {
                    "event_id": "51626",
                    "start_time": "2023/06/14 19:45:00",
                    "duration": "00:30:00",
                    "running_status": 1,
                    "free_CA_mode": False,
                    "short_event": [
                        {
                            "language_code": "DEU",
                            "event_name": "heute journal",
                            "text_char": "Wetter",
                        }
                    ],
                },
            ],
        }
    )

    assert sm.state == State.BUFFERING
    assert sm.chanKey == 2
    assert sm.duration is None
    assert sm.position is None
    assert sm.program_current.short_event[0].event_name == "Aktenzeichen XY... Ungelöst"

    sm.on_event_play_content(
        {"new_play_mode": 4, "playBackState": 1, "mediaType": 1, "mediaCode": "3733"}
    )

    assert sm.state == State.PLAYING
    assert sm.chanKey == 2
    assert sm.duration == 0
    assert sm.position == 0
    assert sm.program_current.short_event[0].event_name == "Aktenzeichen XY... Ungelöst"

    for _ in range(4):
        sm.on_poll_player_state(
            {
                "chanKey": "2",
                "mediaCode": "3733",
                "mediaType": "1",
                "playBackState": "1",
            }
        )

        assert sm.state == State.PLAYING
        assert sm.chanKey == 2
        assert sm.duration == 0
        assert sm.position == 0
        assert (
            sm.program_current.short_event[0].event_name
            == "Aktenzeichen XY... Ungelöst"
        )

    # later
    sm.on_poll_player_state(
        {
            "chanKey": "2",
            "duration": "783",
            "mediaCode": "3733",
            "mediaType": "1",
            "playBackState": "1",
            "playPostion": "783",
        }
    )

    assert sm.state == State.PLAYING
    assert sm.chanKey == 2
    assert sm.duration == 783
    assert sm.position == 783
    assert sm.program_current.short_event[0].event_name == "Aktenzeichen XY... Ungelöst"


def test_on_pause_then_play():
    # start HA, MR is ON
    sm = MediaReceiverStateMachine()
    assert_unknwon(sm)

    sm.on_poll_player_state(
        {
            "chanKey": "2",
            "duration": "1703",
            "mediaCode": "3733",
            "mediaType": "1",
            "playBackState": "1",
            "playPostion": "1703",
        }
    )
    assert sm.state == State.PLAYING
    assert sm.chanKey == 2
    assert sm.duration == 1703
    assert sm.position == 1703

    # press pause button

    sm.on_event_play_content(
        {
            "new_play_mode": 1,
            "playBackState": 1,
            "mediaType": 1,
            "mediaCode": "3733",
            "duration": 1721,
            "playPostion": 1718,
            "fastSpeed": 0,
        }
    )
    assert sm.state == State.PAUSED
    assert sm.chanKey == 2
    assert sm.duration == 1721
    assert sm.position == 1718

    sm.on_poll_player_state(
        {
            "chanKey": "2",
            "duration": "1723",
            "fastSpeed": "0",
            "mediaCode": "3733",
            "mediaType": "1",
            "playBackState": "1",
            "playPostion": "1718",
        }
    )
    assert sm.state == State.PAUSED
    assert sm.chanKey == 2
    assert sm.duration == 1723
    assert sm.position == 1718

    sm.on_poll_player_state(
        {
            "chanKey": "2",
            "duration": "1733",
            "fastSpeed": "0",
            "mediaCode": "3733",
            "mediaType": "1",
            "playBackState": "1",
            "playPostion": "1718",
        }
    )
    assert sm.state == State.PAUSED
    assert sm.chanKey == 2
    assert sm.duration == 1733
    assert sm.position == 1718

    # play
    sm.on_event_play_content(
        {
            "new_play_mode": 2,
            "playBackState": 1,
            "mediaType": 1,
            "mediaCode": "3733",
            "duration": 1743,
            "playPostion": 1718,
            "fastSpeed": 1,
        }
    )
    assert sm.state == State.PLAYING
    assert sm.chanKey == 2
    assert sm.duration == 1743
    assert sm.position == 1718

    sm.on_poll_player_state(
        {
            "chanKey": "2",
            "duration": "1743",
            "fastSpeed": "1",
            "mediaCode": "3733",
            "mediaType": "1",
            "playBackState": "1",
            "playPostion": "1719",
        }
    )
    assert sm.state == State.PLAYING
    assert sm.chanKey == 2
    assert sm.duration == 1743
    assert sm.position == 1719

    sm.on_poll_player_state(
        {
            "chanKey": "2",
            "duration": "1753",
            "fastSpeed": "1",
            "mediaCode": "3733",
            "mediaType": "1",
            "playBackState": "1",
            "playPostion": "1728",
        }
    )
    assert sm.state == State.PLAYING
    assert sm.chanKey == 2
    assert sm.duration == 1753
    assert sm.position == 1728
