from enum import Enum

from .api_event import ProgramInfo


class State(str, Enum):
    """State of media receiver."""

    OFF = "off"
    PLAYING = "playing"
    PAUSED = "paused"
    BUFFERING = "buffering"


class MediaReceiverStateMachine:
    state: State | None = None
    duration: int | None = None
    position: int | None = None
    chanKey: int | None = None

    program_current: ProgramInfo | None = None
    program_next: ProgramInfo | None = None

    _last_poll_player_state = None
    _last_event_play_content = None
    _last_event_eit_changed = None

    _ignore_next_poll_event = False

    def on_event_eit_changed(self, data: dict) -> None:
        if self._last_event_play_content == data:
            return

        self._on_event_eit_changed_changed(data)

        self._last_event_play_content = data

    def _on_event_eit_changed_changed(self, data) -> None:
        if "channel_num" in data:
            self.chanKey = int(data["channel_num"])

        if "program_info" in data:
            programm_info = data["program_info"]
            self.program_current = ProgramInfo(**programm_info[0])
            self.program_next = ProgramInfo(**programm_info[1])

    def on_event_play_content(self, data: dict) -> None:
        if self._last_event_play_content == data:
            return

        self._on_event_play_content_changed(data)

        self._last_event_play_content = data

    def _on_event_play_content_changed(self, data: dict) -> None:
        if "new_play_mode" in data:
            if data["new_play_mode"] == 20:
                self.state = State.BUFFERING
                self.duration = None
                self.position = None

                # poll api is always lagging behind. To prevent switching back and forth we ignore the next event and wait for a change
                self._ignore_next_poll_event = True
                return
            # [2, 3, 4, 5]
            elif data["new_play_mode"] == 4:
                self.state = State.PLAYING
                self.duration = 0
                self.position = 0
                # poll api is always lagging behind. To prevent switching back and forth we ignore the next event and wait for a change
                self._ignore_next_poll_event = True
                return

            elif data["new_play_mode"] == 2:
                # play after pause -> time shift ?
                self.state = State.PLAYING
                self.duration = data["duration"]
                self.position = data["playPostion"]
                return

            elif data["new_play_mode"] == 1:
                self.state = State.PAUSED
                self.duration = data["duration"]
                self.position = data["playPostion"]
                return

            elif data["new_play_mode"] == 0:
                self.state = State.OFF
                self._clear_non_state_attributes()
                return

    def on_poll_player_state(self, data: dict) -> None:
        if self._last_poll_player_state == data:
            return

        self._on_poll_player_state_changed(data)

        self._last_poll_player_state = data

    def _on_poll_player_state_changed(self, data: dict) -> None:
        # deep sleep ?
        if {"playBackState"} == set(data.keys()):
            if data["playBackState"] == "0":
                self.state = State.OFF
                self._clear_non_state_attributes()
            return

        # tv running
        if {
            "chanKey",
            "duration",
            "mediaCode",
            "mediaType",
            "playBackState",
            "playPostion",
        } <= data.keys():
            if "fastSpeed" in data and data["fastSpeed"] == "0":
                self.state = State.PAUSED
            else:
                if self.state != State.PLAYING:
                    self.state = State.PLAYING

            self.chanKey = int(data["chanKey"])
            self.duration = int(data["duration"])
            self.position = int(data["playPostion"])
            return

        if {
            "chanKey",
            "mediaCode",
            "mediaType",
            "playBackState",
        } == set(data.keys()):
            if self._last_poll_player_state is not None:
                # this is an update and NOT the initial poll
                if not self._ignore_next_poll_event:
                    self._ignore_next_poll_event = False
                    if self.state != State.OFF:
                        self.state = State.OFF
                        self._clear_non_state_attributes()
            return

    def _clear_non_state_attributes(self):
        self.chanKey = None
        self.duration = None
        self.position = None

        self.program_current = None
        self.program_next = None
