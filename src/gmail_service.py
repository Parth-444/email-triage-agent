import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build

class GmailClient:
    def __init__(self, credentials):
        self.service = build('gmail', 'v1', credentials=credentials)
        all_Labels = self.service.users().labels().list(userId='me').execute()
        existing_labels = all_Labels.get('labels', []) 
        self.labels = {label['name']: label['id'] for label in existing_labels}

    def watch_mailbox(self, topic_name: str):
        """Register Gmail push notifications to Pub/Sub topic."""
        request = {
            'labelIds': ['INBOX'],
            'topicName': topic_name
        }
        return self.service.users().watch(userId='me', body=request).execute()

    def get_email(self, msg_id: str):
        """Fetch raw email content and thread."""
        return self.service.users().messages().get(userId='me', id=msg_id, format='full').execute()

    def create_draft(self, to_email: str, thread_id: str, subject: str, body_text: str):
        """Create an email draft in the customer thread for human review."""
        message = MIMEText(body_text)
        message['to'] = to_email
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body = {'message': {'raw': raw, 'threadId': thread_id}}
        return self.service.users().drafts().create(userId='me', body=body).execute()

    def send_reply(self, to_email: str, thread_id: str, subject: str, body_text: str):
        """Directly send auto-response."""
        message = MIMEText(body_text)
        message['to'] = to_email
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body = {'raw': raw, 'threadId': thread_id}
        return self.service.users().messages().send(userId='me', body=body).execute()

    def apply_label(self, msg_id: str, label_name: str):
        """Add organizational triage labels."""
        # Fetches/creates label ID and modifies message labels
        if label_name in self.labels:
            self.service.users().messages().modify(
                            userId='me',
                            id = msg_id,
                            body = {'addLabelIds': [self.labels[label_name]]}
                        ).execute()
            return label_name
        else:
            label = self.service.users().labels().create(userId='me', body={'name': label_name}).execute()
            self.labels[label_name] = label['id']
            self.service.users().messages().modify(
                userId='me',
                id = msg_id,
                body = {'addLabelIds': [self.labels[label_name]]}
            ).execute()
            return label_name
        