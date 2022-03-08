import os
import logging
from slack import WebClient
from slack.signature import SignatureVerifier
from slack.web.classes.objects import PlainTextObject, TextObject, MarkdownTextObject
from slack.web.classes.elements import ChannelSelectElement, DatePickerElement, PlainTextInputElement, ButtonElement
from slack.web.classes.blocks import InputBlock, ContextBlock, SectionBlock, DividerBlock
from slack.web.classes.views import View
from slack.errors import SlackApiError
import requests
from flask import Flask, request, make_response, Response
import json
import datetime
import re


# Initialize a Flask app to host the events adapter
app = Flask(__name__)
slack_token = "xoxb-placeholder"
# Initialize a Web API client
#slack_client = WebClient(token=os.environ['SLACK_API_TOKEN'])
slack_client = WebClient(token=slack_token)

signature_verifier = SignatureVerifier("sig-placeholder")

@app.route('/slack/events', methods=['POST'])
def message_actions():
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        return make_response("invalid request", 403)
    if "payload" in request.form:
        payload = json.loads(request.form["payload"])
        print(payload)
        if payload["type"] == "shortcut" \
            and payload["callback_id"] == "hang-post-open":
            try:
                view = View(
                    type="modal",
                    callback_id="hang-post-submit",
                    title=PlainTextObject(text="Create a Hang"),
                    submit=PlainTextObject(text="Post"),
                    close=PlainTextObject(text="Cancel"),
                    blocks=[
                        InputBlock(
                            block_id="where-id",
                            label=PlainTextObject(text="Where:"),
                            element=PlainTextInputElement(
                                action_id="where-action",
                            )
                        ),
                        InputBlock(
                            block_id="when-id",
                            label=PlainTextObject(text="When:"),
                            element=DatePickerElement(
                                action_id="when-action",
                                initial_date=datetime.date.today().strftime("%Y-%m-%d"),
                            )
                        ),
                        InputBlock(
                            block_id="min-amount-id",
                            label=PlainTextObject(text="Reveal Count:"),
                            element=PlainTextInputElement(
                                action_id="min-amount-action",
                            )
                        ),
                        InputBlock(
                            block_id="channel-id",
                            label=PlainTextObject(text="Channel:"),
                            element=ChannelSelectElement(
                                action_id="channel-action",
                            )
                        ),
                    ]
                )
                slack_client.views_open(
                    trigger_id=payload["trigger_id"],
                    view=view
                )

                return Response(), 200
                #return make_response("", 200)
            except SlackApiError as e:
                code = e.response["error"]
                return make_response(f"Failed to open a modal due to {code}", 200)
            return Response(), 404

        if payload["type"] == "view_submission" \
            and payload["view"]["callback_id"] == "hang-post-submit":
            # Handle a data submission request from the modal
            try:
                submitted_data = payload["view"]["state"]["values"]
                rsvp_info = payload["user"]["username"]
                print(submitted_data)  # {'b-id': {'a-id': {'type': 'plain_text_input', 'value': 'your input'}}}
                where_value = submitted_data["where-id"]["where-action"]["value"]
                when_value = submitted_data["when-id"]["when-action"]["selected_date"]
                min_amount_value = submitted_data["min-amount-id"]["min-amount-action"]["value"]
                channel_value = submitted_data["channel-id"]["channel-action"]["selected_channel"]
                current_amount_value = 1
                print(min_amount_value.isdigit())
                if not min_amount_value.isdigit() or int(min_amount_value) <= 1:
                    raise ValueError("Invalid Value, Reveal Count Must be a number above 1!")
                slack_client.chat_postMessage(
                    channel=channel_value,
                    username="HangBot - New Hang!",
                    blocks=[
                        SectionBlock(
                            block_id="intro_section-id",
                            text=MarkdownTextObject(
                                text="A new Hang has been initiated! :eyes:",
                            )
                        ),
                        DividerBlock(),
                        SectionBlock(
                            block_id="where_section-id",
                            text=MarkdownTextObject(
                                text=":round_pushpin: Where: *{}*".format(where_value),
                            )
                        ),
                        SectionBlock(
                            block_id="when_section-id",
                            text=MarkdownTextObject(
                                text=":clock1: When: *{}*".format(when_value),
                            )
                        ),
                        SectionBlock(
                            block_id="rsvp_section-id",
                            text=MarkdownTextObject(
                                text=":lock: RSVP: *{0}/{1}* :arrow_left: everyone will be revealed once {1} join! ".format(current_amount_value,min_amount_value)
                            ),
                            accessory=ButtonElement(
                                text=PlainTextObject(text=":palms_up_together: I'm Down!"),
                                action_id="rsvp_button",
                                value="Creator: #{0} \n Participants: ".format(rsvp_info),
                                style="primary",
                            ),
                        ),
                    ]
                )

                return Response(), 200
            except ValueError as e:
                response = {
                    "response_action": "errors",
                    "errors": {
                        "min-amount-id": str(e)
                    }
                }
                return response
        if payload["type"] == "block_actions" \
            and payload["actions"][0]["action_id"] == "rsvp_button":
            rsvp_list = payload["actions"][0]["value"]
            rsvp_info = payload["user"]["username"]
            if rsvp_info in rsvp_list:
                return Response(), 200
            else:
                rsvp_list += " #" + rsvp_info
            channel_value = payload["channel"]["id"]
            message_timestamp = payload["message"]["ts"]
            where_value = payload["message"]["blocks"][2]["text"]["text"].split("*")[1]
            when_value = payload["message"]["blocks"][3]["text"]["text"].split("*")[1]
            rsvp_ratio = payload["message"]["blocks"][4]["text"]["text"].split("*")[1]
            current_amount_value, min_amount_value = re.split('/|\*', rsvp_ratio)
            min_amount_value = int(min_amount_value)
            current_amount_value = int(current_amount_value)
            current_amount_value += 1
            if current_amount_value >= min_amount_value:
                slack_client.chat_update(
                    channel=channel_value,
                    username="HangBot - New Hang!",
                    ts=message_timestamp,
                    blocks=[
                        SectionBlock(
                            block_id="intro_section-id",
                            text=MarkdownTextObject(
                                text="A new Hang has been initiated! :eyes:",
                            )
                        ),
                        DividerBlock(),
                        SectionBlock(
                            block_id="where_section-id",
                            text=MarkdownTextObject(
                                text=":round_pushpin: Where: *{}*".format(where_value),
                            )
                        ),
                        SectionBlock(
                            block_id="when_section-id",
                            text=MarkdownTextObject(
                                text=":clock1: When: *{}*".format(when_value),
                            )
                        ),
                        SectionBlock(
                            block_id="rsvp_section-id",
                            text=MarkdownTextObject(
                                text=":unlock: RSVP: *{0}/{1}* :arrow_left: Reached RSVP Amount! ".format(current_amount_value,min_amount_value)
                            ),
                            accessory=ButtonElement(
                                text=PlainTextObject(text=":palms_up_together: I'm Down!"),
                                action_id="rsvp_button",
                                value=rsvp_list,
                                style="primary",
                            ),
                        ),
                        SectionBlock(
                            block_id="participants_section-id",
                            text=MarkdownTextObject(
                                text=":confetti_ball: {} ".format(rsvp_list),
                            )
                        ),
                    ]
                )
                return Response(), 200

            slack_client.chat_update(
                channel=channel_value,
                username="HangBot - New Hang!",
                ts=message_timestamp,
                blocks=[
                    SectionBlock(
                        block_id="intro_section-id",
                        text=MarkdownTextObject(
                            text="A new Hang has been initiated! :eyes:",
                        )
                    ),
                    DividerBlock(),
                    SectionBlock(
                        block_id="where_section-id",
                        text=MarkdownTextObject(
                            text=":round_pushpin: Where: *{}*".format(where_value),
                        )
                    ),
                    SectionBlock(
                        block_id="when_section-id",
                        text=MarkdownTextObject(
                            text=":clock1: When: *{}*".format(when_value),
                        )
                    ),
                    SectionBlock(
                        block_id="rsvp_section-id",
                        text=MarkdownTextObject(
                            text=":lock: RSVP: *{0}/{1}* :arrow_left: everyone will be revealed once {1} join! ".format(current_amount_value,min_amount_value)
                        ),
                        accessory=ButtonElement(
                            text=PlainTextObject(text=":palms_up_together: I'm Down!"),
                            action_id="rsvp_button",
                            value=rsvp_list,
                            style="primary",
                        ),
                    ),
                ]
            )
            return Response(), 200
    return Response(), 404

if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    app.run(debug=True,use_reloader=False,port=3000)