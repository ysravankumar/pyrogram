# Pyrogram - Telegram MTProto API Client Library for Python
# Copyright (C) 2017-2019 Dan Tès <https://github.com/delivrance>
#
# This file is part of Pyrogram.
#
# Pyrogram is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pyrogram is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pyrogram.  If not, see <http://www.gnu.org/licenses/>.

import binascii
import os
import struct
from typing import Union

import pyrogram
from pyrogram.api import functions, types
from pyrogram.errors import FileIdInvalid, FilePartMissing
from pyrogram.client.ext import BaseClient, utils


class SendAudio(BaseClient):
    def send_audio(
        self,
        chat_id: Union[int, str],
        audio: str,
        caption: str = "",
        parse_mode: str = "",
        duration: int = 0,
        performer: str = None,
        title: str = None,
        thumb: str = None,
        disable_notification: bool = None,
        reply_to_message_id: int = None,
        reply_markup: Union[
            "pyrogram.InlineKeyboardMarkup",
            "pyrogram.ReplyKeyboardMarkup",
            "pyrogram.ReplyKeyboardRemove",
            "pyrogram.ForceReply"
        ] = None,
        progress: callable = None,
        progress_args: tuple = ()
    ) -> Union["pyrogram.Message", None]:
        """Send audio files.

        For sending voice messages, use the :obj:`send_voice()` method instead.

        Parameters:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.
                For your personal cloud (Saved Messages) you can simply use "me" or "self".
                For a contact that exists in your Telegram address book you can use his phone number (str).

            audio (``str``):
                Audio file to send.
                Pass a file_id as string to send an audio file that exists on the Telegram servers,
                pass an HTTP URL as a string for Telegram to get an audio file from the Internet, or
                pass a file path as string to upload a new audio file that exists on your local machine.

            caption (``str``, *optional*):
                Audio caption, 0-1024 characters.

            parse_mode (``str``, *optional*):
                Pass "markdown" or "html" if you want Telegram apps to show bold, italic, fixed-width text or inline
                URLs in your caption. Defaults to "markdown".

            duration (``int``, *optional*):
                Duration of the audio in seconds.

            performer (``str``, *optional*):
                Performer.

            title (``str``, *optional*):
                Track name.

            thumb (``str``, *optional*):
                Thumbnail of the music file album cover.
                The thumbnail should be in JPEG format and less than 200 KB in size.
                A thumbnail's width and height should not exceed 320 pixels.
                Thumbnails can't be reused and can be only uploaded as a new file.

            disable_notification (``bool``, *optional*):
                Sends the message silently.
                Users will receive a notification with no sound.

            reply_to_message_id (``int``, *optional*):
                If the message is a reply, ID of the original message.

            reply_markup (:obj:`InlineKeyboardMarkup` | :obj:`ReplyKeyboardMarkup` | :obj:`ReplyKeyboardRemove` | :obj:`ForceReply`, *optional*):
                Additional interface options. An object for an inline keyboard, custom reply keyboard,
                instructions to remove reply keyboard or to force a reply from the user.

            progress (``callable``, *optional*):
                Pass a callback function to view the upload progress.
                The function must take *(client, current, total, \*args)* as positional arguments (look at the section
                below for a detailed description).

            progress_args (``tuple``, *optional*):
                Extra custom arguments for the progress callback function. Useful, for example, if you want to pass
                a chat_id and a message_id in order to edit a message with the updated progress.

        Other Parameters:
            client (:obj:`Client`):
                The Client itself, useful when you want to call other API methods inside the callback function.

            current (``int``):
                The amount of bytes uploaded so far.

            total (``int``):
                The size of the file.

            *args (``tuple``, *optional*):
                Extra custom arguments as defined in the *progress_args* parameter.
                You can either keep *\*args* or add every single extra argument in your function signature.

        Returns:
            :obj:`Message`: On success, the sent audio message is returned.

            ``None`` -- In case the upload is deliberately stopped with :meth:`stop_transmission`.

        Raises:
            RPCError: In case of a Telegram RPC error.
        """
        file = None
        style = self.html if parse_mode.lower() == "html" else self.markdown

        try:
            if os.path.exists(audio):
                thumb = None if thumb is None else self.save_file(thumb)
                file = self.save_file(audio, progress=progress, progress_args=progress_args)
                media = types.InputMediaUploadedDocument(
                    mime_type=self.guess_mime_type(audio) or "audio/mpeg",
                    file=file,
                    thumb=thumb,
                    attributes=[
                        types.DocumentAttributeAudio(
                            duration=duration,
                            performer=performer,
                            title=title
                        ),
                        types.DocumentAttributeFilename(file_name=os.path.basename(audio))
                    ]
                )
            elif audio.startswith("http"):
                media = types.InputMediaDocumentExternal(
                    url=audio
                )
            else:
                try:
                    decoded = utils.decode(audio)
                    fmt = "<iiqqqqi" if len(decoded) > 24 else "<iiqq"
                    unpacked = struct.unpack(fmt, decoded)
                except (AssertionError, binascii.Error, struct.error):
                    raise FileIdInvalid from None
                else:
                    if unpacked[0] != 9:
                        media_type = BaseClient.MEDIA_TYPE_ID.get(unpacked[0], None)

                        if media_type:
                            raise FileIdInvalid("The file_id belongs to a {}".format(media_type))
                        else:
                            raise FileIdInvalid("Unknown media type: {}".format(unpacked[0]))

                    media = types.InputMediaDocument(
                        id=types.InputDocument(
                            id=unpacked[2],
                            access_hash=unpacked[3],
                            file_reference=b""
                        )
                    )

            while True:
                try:
                    r = self.send(
                        functions.messages.SendMedia(
                            peer=self.resolve_peer(chat_id),
                            media=media,
                            silent=disable_notification or None,
                            reply_to_msg_id=reply_to_message_id,
                            random_id=self.rnd_id(),
                            reply_markup=reply_markup.write() if reply_markup else None,
                            **style.parse(caption)
                        )
                    )
                except FilePartMissing as e:
                    self.save_file(audio, file_id=file.id, file_part=e.x)
                else:
                    for i in r.updates:
                        if isinstance(i, (types.UpdateNewMessage, types.UpdateNewChannelMessage)):
                            return pyrogram.Message._parse(
                                self, i.message,
                                {i.id: i for i in r.users},
                                {i.id: i for i in r.chats}
                            )
        except BaseClient.StopTransmission:
            return None
