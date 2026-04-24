# Rich Notification Samples

This document provides practical JSON samples for each common use case. All samples follow the rules defined in `richnotification_rule.txt`.

---

## Sample 1: Simple Read-Only Notification (Label Only)

A basic announcement message with no user interaction. No callback needed.

```json
{
    "richnotification": {
        "header": {
            "from": "2067928",
            "token": "YOUR_CUBE_BOT_TOKEN",
            "fromusername": ["알림봇", "Notification Bot", "", "", ""],
            "to": {
                "uniquename": ["X905552"],
                "channelid": [""]
            }
        },
        "content": [{
            "header": {},
            "body": {
                "bodystyle": "none",
                "row": [
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["시스템 점검 안내", "System Maintenance Notice", "", "", ""],
                                    "color": "#000000"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["2026년 4월 20일 22:00 ~ 04:00 서버 점검이 예정되어 있습니다.", "Server maintenance scheduled for April 20, 2026, 22:00 ~ 04:00.", "", "", ""],
                                    "color": "#666666"
                                }
                            }
                        ]
                    }
                ]
            },
            "process": {
                "callbacktype": "url",
                "callbackaddress": "",
                "processdata": "",
                "processtype": "",
                "summary": ["", "", "", "", ""],
                "session": {
                    "sessionid": "",
                    "sequence": ""
                },
                "mandatory": [],
                "requestid": []
            }
        }],
        "result": ""
    }
}
```

---

## Sample 2: Approval Form (Label + Buttons + Callback)

A leave approval request with Approve/Reject buttons that post back to a callback URL.

```json
{
    "richnotification": {
        "header": {
            "from": "2067928",
            "token": "YOUR_CUBE_BOT_TOKEN",
            "fromusername": ["결재봇", "Approval Bot", "", "", ""],
            "to": {
                "uniquename": ["X905552"],
                "channelid": [""]
            }
        },
        "content": [{
            "header": {},
            "body": {
                "bodystyle": "none",
                "row": [
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["[결재 요청] 휴가 신청서", "[Approval Request] Leave Application", "", "", ""],
                                    "color": "#000000"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["신청자: 홍길동 / 기간: 2026-04-20 ~ 2026-04-22", "Applicant: Hong Gildong / Period: 2026-04-20 ~ 2026-04-22", "", "", ""],
                                    "color": "#666666"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "center",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "center",
                                "valign": "middle",
                                "width": "50%",
                                "type": "button",
                                "control": {
                                    "processid": "AgreeButton",
                                    "active": true,
                                    "text": ["승인", "Approve", "", "", ""],
                                    "confirmmsg": "승인하시겠습니까?",
                                    "value": "approve",
                                    "bgcolor": "#4CAF50",
                                    "textcolor": "#ffffff",
                                    "align": "center",
                                    "clickurl": "",
                                    "androidurl": "",
                                    "iosurl": "",
                                    "popupoption": "",
                                    "sso": false,
                                    "inner": false
                                }
                            },
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "center",
                                "valign": "middle",
                                "width": "50%",
                                "type": "button",
                                "control": {
                                    "processid": "RejectButton",
                                    "active": true,
                                    "text": ["반려", "Reject", "", "", ""],
                                    "confirmmsg": "반려하시겠습니까?",
                                    "value": "reject",
                                    "bgcolor": "#FF0000",
                                    "textcolor": "#ffffff",
                                    "align": "center",
                                    "clickurl": "",
                                    "androidurl": "",
                                    "iosurl": "",
                                    "popupoption": "",
                                    "sso": false,
                                    "inner": false
                                }
                            }
                        ]
                    }
                ]
            },
            "process": {
                "callbacktype": "url",
                "callbackaddress": "http://10.158.121.214:17614/chatbot/chat/cube",
                "processdata": "",
                "processtype": "",
                "summary": ["", "", "", "", ""],
                "session": {
                    "sessionid": "Bot_Approval_0001",
                    "sequence": "1"
                },
                "mandatory": [],
                "requestid": ["AgreeButton", "RejectButton", "cubeuniquename", "cubechannelid", "cubeaccountid", "cubelanguagetype", "cubemessageid"]
            }
        }],
        "result": ""
    }
}
```

---

## Sample 3: Survey Form (Radio + Checkbox + Select + InputText)

An employee satisfaction survey combining multiple input types with mandatory validation.

```json
{
    "richnotification": {
        "header": {
            "from": "2067928",
            "token": "YOUR_CUBE_BOT_TOKEN",
            "fromusername": ["설문봇", "Survey Bot", "", "", ""],
            "to": {
                "uniquename": ["X905552"],
                "channelid": [""]
            }
        },
        "content": [{
            "header": {},
            "body": {
                "bodystyle": "none",
                "row": [
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["[설문] 직원 만족도 조사", "[Survey] Employee Satisfaction", "", "", ""],
                                    "color": "#000000"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["1. 전반적인 만족도를 선택해 주세요.", "1. Please select your overall satisfaction.", "", "", ""],
                                    "color": "#333333"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "33%",
                                "type": "radio",
                                "control": {
                                    "processid": "Survey1",
                                    "active": true,
                                    "text": ["만족", "Satisfied", "", "", ""],
                                    "value": "1",
                                    "checked": false
                                }
                            },
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "33%",
                                "type": "radio",
                                "control": {
                                    "processid": "Survey1",
                                    "active": true,
                                    "text": ["보통", "Neutral", "", "", ""],
                                    "value": "2",
                                    "checked": true
                                }
                            },
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "33%",
                                "type": "radio",
                                "control": {
                                    "processid": "Survey1",
                                    "active": true,
                                    "text": ["불만족", "Dissatisfied", "", "", ""],
                                    "value": "3",
                                    "checked": false
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["2. 관심 분야를 선택해 주세요. (복수 선택 가능)", "2. Select areas of interest. (Multiple selection)", "", "", ""],
                                    "color": "#333333"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "50%",
                                "type": "checkbox",
                                "control": {
                                    "processid": "Sentence",
                                    "active": true,
                                    "text": ["복지", "Welfare", "", "", ""],
                                    "value": "welfare",
                                    "checked": false
                                }
                            },
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "50%",
                                "type": "checkbox",
                                "control": {
                                    "processid": "Sentence",
                                    "active": true,
                                    "text": ["교육", "Education", "", "", ""],
                                    "value": "education",
                                    "checked": false
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["3. 소속 부서를 선택해 주세요.", "3. Select your department.", "", "", ""],
                                    "color": "#333333"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "select",
                                "control": {
                                    "processid": "SelectContent",
                                    "active": true,
                                    "text": ["부서 선택", "Select Department", "", "", ""],
                                    "item": [
                                        {
                                            "text": ["개발팀", "Development", "", "", ""],
                                            "value": "dev",
                                            "selected": false
                                        },
                                        {
                                            "text": ["기획팀", "Planning", "", "", ""],
                                            "value": "plan",
                                            "selected": false
                                        },
                                        {
                                            "text": ["인사팀", "HR", "", "", ""],
                                            "value": "hr",
                                            "selected": true
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["4. 추가 의견을 입력해 주세요.", "4. Please enter additional comments.", "", "", ""],
                                    "color": "#333333"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "inputtext",
                                "control": {
                                    "processid": "Comment",
                                    "active": true,
                                    "text": ["의견", "Comment", "", "", ""],
                                    "value": "",
                                    "width": "100%",
                                    "minlength": -1,
                                    "maxlength": 200,
                                    "placeholder": ["의견을 입력하세요", "Enter your comment", "", "", ""],
                                    "validmsg": ["200자 이내로 입력해 주세요.", "Please enter within 200 characters.", "", "", ""]
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "center",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "center",
                                "valign": "middle",
                                "width": "100%",
                                "type": "button",
                                "control": {
                                    "processid": "SendButton",
                                    "active": true,
                                    "text": ["제출", "Submit", "", "", ""],
                                    "confirmmsg": "설문을 제출하시겠습니까?",
                                    "value": "submit",
                                    "bgcolor": "#1976D2",
                                    "textcolor": "#ffffff",
                                    "align": "center",
                                    "clickurl": "",
                                    "androidurl": "",
                                    "iosurl": "",
                                    "popupoption": "",
                                    "sso": false,
                                    "inner": false
                                }
                            }
                        ]
                    }
                ]
            },
            "process": {
                "callbacktype": "url",
                "callbackaddress": "http://10.158.121.214:17614/chatbot/chat/cube",
                "processdata": "",
                "processtype": "",
                "summary": ["", "", "", "", ""],
                "session": {
                    "sessionid": "Bot_Survey_0001",
                    "sequence": "1"
                },
                "mandatory": [
                    {
                        "processid": "Survey1",
                        "alertmsg": ["만족도를 선택해 주세요.", "Please select satisfaction level.", "", "", ""]
                    },
                    {
                        "processid": "SelectContent",
                        "alertmsg": ["부서를 선택해 주세요.", "Please select a department.", "", "", ""]
                    }
                ],
                "requestid": ["Survey1", "Sentence", "SelectContent", "Comment", "SendButton", "cubeuniquename", "cubechannelid", "cubeaccountid", "cubelanguagetype", "cubemessageid"]
            }
        }],
        "result": ""
    }
}
```

---

## Sample 4: Date Selection Form (DatePicker + DateTimePicker + Textarea)

A meeting room reservation form with date/time pickers, a textarea for notes, and mandatory validation.

```json
{
    "richnotification": {
        "header": {
            "from": "2067928",
            "token": "YOUR_CUBE_BOT_TOKEN",
            "fromusername": ["회의실봇", "Room Bot", "", "", ""],
            "to": {
                "uniquename": ["X905552"],
                "channelid": [""]
            }
        },
        "content": [{
            "header": {},
            "body": {
                "bodystyle": "none",
                "row": [
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["[회의실 예약]", "[Room Reservation]", "", "", ""],
                                    "color": "#000000"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["예약 날짜를 선택하세요.", "Select reservation date.", "", "", ""],
                                    "color": "#333333"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "50%",
                                "type": "datepicker",
                                "control": {
                                    "processid": "SelectDate",
                                    "active": true,
                                    "text": ["예약일", "Date", "", "", ""],
                                    "value": "2026/04/20"
                                }
                            },
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "50%",
                                "type": "datetimepicker",
                                "control": {
                                    "processid": "SelectDateTime",
                                    "active": true,
                                    "text": ["시작 시간", "Start Time", "", "", ""],
                                    "value": "2026/04/20 14:00"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["회의 내용을 입력하세요.", "Enter meeting details.", "", "", ""],
                                    "color": "#333333"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "textarea",
                                "control": {
                                    "processid": "Comment",
                                    "active": true,
                                    "text": ["회의 내용", "Meeting Details", "", "", ""],
                                    "value": "",
                                    "minlength": 5,
                                    "maxlength": 500,
                                    "width": "100%",
                                    "height": "100px",
                                    "placeholder": ["회의 주제 및 참석자를 입력하세요", "Enter meeting topic and attendees", "", "", ""],
                                    "validmsg": ["5자 이상 500자 이내로 입력해 주세요.", "Please enter between 5 and 500 characters.", "", "", ""]
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "center",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "center",
                                "valign": "middle",
                                "width": "100%",
                                "type": "button",
                                "control": {
                                    "processid": "SendButton",
                                    "active": true,
                                    "text": ["예약 신청", "Reserve", "", "", ""],
                                    "confirmmsg": "회의실을 예약하시겠습니까?",
                                    "value": "reserve",
                                    "bgcolor": "#1976D2",
                                    "textcolor": "#ffffff",
                                    "align": "center",
                                    "clickurl": "",
                                    "androidurl": "",
                                    "iosurl": "",
                                    "popupoption": "",
                                    "sso": false,
                                    "inner": false
                                }
                            }
                        ]
                    }
                ]
            },
            "process": {
                "callbacktype": "url",
                "callbackaddress": "http://10.158.121.214:17614/chatbot/chat/cube",
                "processdata": "",
                "processtype": "",
                "summary": ["", "", "", "", ""],
                "session": {
                    "sessionid": "Bot_Room_0001",
                    "sequence": "1"
                },
                "mandatory": [
                    {
                        "processid": "SelectDate",
                        "alertmsg": ["날짜를 선택해 주세요.", "Please select a date.", "", "", ""]
                    },
                    {
                        "processid": "Comment",
                        "alertmsg": ["회의 내용을 입력해 주세요.", "Please enter meeting details.", "", "", ""]
                    }
                ],
                "requestid": ["SelectDate", "SelectDateTime", "Comment", "SendButton", "cubeuniquename", "cubechannelid", "cubeaccountid", "cubelanguagetype", "cubemessageid"]
            }
        }],
        "result": ""
    }
}
```

---

## Sample 5: Image Card with HyperText Link

A promotional card with an image and a clickable link.

```json
{
    "richnotification": {
        "header": {
            "from": "2067928",
            "token": "YOUR_CUBE_BOT_TOKEN",
            "fromusername": ["홍보봇", "Promo Bot", "", "", ""],
            "to": {
                "channelid": ["CH_GENERAL_001"],
                "uniquename": []
            }
        },
        "content": [{
            "header": {},
            "body": {
                "bodystyle": "none",
                "row": [
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "center",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "center",
                                "valign": "middle",
                                "width": "100%",
                                "type": "image",
                                "control": {
                                    "active": true,
                                    "text": ["사내 행사 배너", "Company Event Banner", "", "", ""],
                                    "linkurl": "https://www.skhystec.com/event",
                                    "androidurl": "",
                                    "iosurl": "",
                                    "popupoption": "",
                                    "location": true,
                                    "sourceurl": "10.158.122.138/Resource/Image/event_banner.png",
                                    "displaytype": "resize",
                                    "width": "100%",
                                    "height": "",
                                    "sso": false,
                                    "inner": true
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["2026 상반기 사내 체육대회가 개최됩니다!", "2026 First Half Company Sports Day!", "", "", ""],
                                    "color": "#000000"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "hypertext",
                                "control": {
                                    "active": true,
                                    "text": ["자세히 보기 >>", "View Details >>", "", "", ""],
                                    "linkurl": "https://www.skhystec.com/event/detail",
                                    "androidurl": "",
                                    "iosurl": "",
                                    "popupoption": "",
                                    "sso": false,
                                    "inner": false,
                                    "opengraph": true
                                }
                            }
                        ]
                    }
                ]
            },
            "process": {
                "callbacktype": "url",
                "callbackaddress": "",
                "processdata": "",
                "processtype": "",
                "summary": ["", "", "", "", ""],
                "session": {
                    "sessionid": "",
                    "sequence": ""
                },
                "mandatory": [],
                "requestid": []
            }
        }],
        "result": ""
    }
}
```

---

## Sample 6: Grid Layout Table (bodystyle: "grid")

A task status report displayed in a table-like grid layout with borders.

```json
{
    "richnotification": {
        "header": {
            "from": "2067928",
            "token": "YOUR_CUBE_BOT_TOKEN",
            "fromusername": ["업무봇", "Task Bot", "", "", ""],
            "to": {
                "uniquename": ["X905552"],
                "channelid": [""]
            }
        },
        "content": [{
            "header": {},
            "body": {
                "bodystyle": "grid",
                "row": [
                    {
                        "bgcolor": "#1976D2",
                        "border": true,
                        "align": "center",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "#1976D2",
                                "border": true,
                                "align": "center",
                                "valign": "middle",
                                "width": "40%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["업무명", "Task Name", "", "", ""],
                                    "color": "#ffffff"
                                }
                            },
                            {
                                "bgcolor": "#1976D2",
                                "border": true,
                                "align": "center",
                                "valign": "middle",
                                "width": "30%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["담당자", "Assignee", "", "", ""],
                                    "color": "#ffffff"
                                }
                            },
                            {
                                "bgcolor": "#1976D2",
                                "border": true,
                                "align": "center",
                                "valign": "middle",
                                "width": "30%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["상태", "Status", "", "", ""],
                                    "color": "#ffffff"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "#ffffff",
                        "border": true,
                        "align": "center",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "#ffffff",
                                "border": true,
                                "align": "left",
                                "valign": "middle",
                                "width": "40%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["API 개발", "API Development", "", "", ""],
                                    "color": "#000000"
                                }
                            },
                            {
                                "bgcolor": "#ffffff",
                                "border": true,
                                "align": "center",
                                "valign": "middle",
                                "width": "30%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["김철수", "Kim Cheolsu", "", "", ""],
                                    "color": "#000000"
                                }
                            },
                            {
                                "bgcolor": "#E8F5E9",
                                "border": true,
                                "align": "center",
                                "valign": "middle",
                                "width": "30%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["완료", "Done", "", "", ""],
                                    "color": "#4CAF50"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "#ffffff",
                        "border": true,
                        "align": "center",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "#ffffff",
                                "border": true,
                                "align": "left",
                                "valign": "middle",
                                "width": "40%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["UI 디자인", "UI Design", "", "", ""],
                                    "color": "#000000"
                                }
                            },
                            {
                                "bgcolor": "#ffffff",
                                "border": true,
                                "align": "center",
                                "valign": "middle",
                                "width": "30%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["이영희", "Lee Younghee", "", "", ""],
                                    "color": "#000000"
                                }
                            },
                            {
                                "bgcolor": "#FFF3E0",
                                "border": true,
                                "align": "center",
                                "valign": "middle",
                                "width": "30%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["진행중", "In Progress", "", "", ""],
                                    "color": "#FF9800"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "#ffffff",
                        "border": true,
                        "align": "center",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "#ffffff",
                                "border": true,
                                "align": "left",
                                "valign": "middle",
                                "width": "40%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["QA 테스트", "QA Testing", "", "", ""],
                                    "color": "#000000"
                                }
                            },
                            {
                                "bgcolor": "#ffffff",
                                "border": true,
                                "align": "center",
                                "valign": "middle",
                                "width": "30%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["박민수", "Park Minsu", "", "", ""],
                                    "color": "#000000"
                                }
                            },
                            {
                                "bgcolor": "#FFEBEE",
                                "border": true,
                                "align": "center",
                                "valign": "middle",
                                "width": "30%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["대기", "Pending", "", "", ""],
                                    "color": "#FF0000"
                                }
                            }
                        ]
                    }
                ]
            },
            "process": {
                "callbacktype": "url",
                "callbackaddress": "",
                "processdata": "",
                "processtype": "",
                "summary": ["", "", "", "", ""],
                "session": {
                    "sessionid": "",
                    "sequence": ""
                },
                "mandatory": [],
                "requestid": []
            }
        }],
        "result": ""
    }
}
```

---

## Sample 7: Rejection Form with Reason Input (Approval + Reject with Reason)

An approval form where rejection requires a mandatory reason via textarea.

```json
{
    "richnotification": {
        "header": {
            "from": "2067928",
            "token": "YOUR_CUBE_BOT_TOKEN",
            "fromusername": ["결재봇", "Approval Bot", "", "", ""],
            "to": {
                "uniquename": ["X905552"],
                "channelid": [""]
            }
        },
        "content": [{
            "header": {},
            "body": {
                "bodystyle": "none",
                "row": [
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["[결재] 구매 요청서 - 모니터 20대", "[Approval] Purchase Request - 20 Monitors", "", "", ""],
                                    "color": "#000000"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["요청자: 박대리 / 금액: 12,000,000원", "Requester: Park / Amount: 12,000,000 KRW", "", "", ""],
                                    "color": "#666666"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "label",
                                "control": {
                                    "active": true,
                                    "text": ["반려 시 사유를 입력해 주세요.", "Please enter reason if rejecting.", "", "", ""],
                                    "color": "#999999"
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "left",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "left",
                                "valign": "middle",
                                "width": "100%",
                                "type": "textarea",
                                "control": {
                                    "processid": "Reason",
                                    "active": true,
                                    "text": ["반려 사유", "Rejection Reason", "", "", ""],
                                    "value": "",
                                    "minlength": -1,
                                    "maxlength": 300,
                                    "width": "100%",
                                    "height": "80px",
                                    "placeholder": ["반려 사유를 입력하세요 (반려 시 필수)", "Enter rejection reason (required for rejection)", "", "", ""],
                                    "validmsg": ["300자 이내로 입력해 주세요.", "Please enter within 300 characters.", "", "", ""]
                                }
                            }
                        ]
                    },
                    {
                        "bgcolor": "",
                        "border": false,
                        "align": "center",
                        "width": "100%",
                        "column": [
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "center",
                                "valign": "middle",
                                "width": "50%",
                                "type": "button",
                                "control": {
                                    "processid": "AgreeButton",
                                    "active": true,
                                    "text": ["승인", "Approve", "", "", ""],
                                    "confirmmsg": "승인하시겠습니까?",
                                    "value": "approve",
                                    "bgcolor": "#4CAF50",
                                    "textcolor": "#ffffff",
                                    "align": "center",
                                    "clickurl": "",
                                    "androidurl": "",
                                    "iosurl": "",
                                    "popupoption": "",
                                    "sso": false,
                                    "inner": false
                                }
                            },
                            {
                                "bgcolor": "",
                                "border": false,
                                "align": "center",
                                "valign": "middle",
                                "width": "50%",
                                "type": "button",
                                "control": {
                                    "processid": "RejectButton",
                                    "active": true,
                                    "text": ["반려", "Reject", "", "", ""],
                                    "confirmmsg": "반려하시겠습니까?",
                                    "value": "reject",
                                    "bgcolor": "#FF0000",
                                    "textcolor": "#ffffff",
                                    "align": "center",
                                    "clickurl": "",
                                    "androidurl": "",
                                    "iosurl": "",
                                    "popupoption": "",
                                    "sso": false,
                                    "inner": false
                                }
                            }
                        ]
                    }
                ]
            },
            "process": {
                "callbacktype": "url",
                "callbackaddress": "http://10.158.121.214:17614/chatbot/chat/cube",
                "processdata": "",
                "processtype": "",
                "summary": ["", "", "", "", ""],
                "session": {
                    "sessionid": "Bot_Purchase_0001",
                    "sequence": "1"
                },
                "mandatory": [],
                "requestid": ["AgreeButton", "RejectButton", "Reason", "cubeuniquename", "cubechannelid", "cubeaccountid", "cubelanguagetype", "cubemessageid"]
            }
        }],
        "result": ""
    }
}
```
