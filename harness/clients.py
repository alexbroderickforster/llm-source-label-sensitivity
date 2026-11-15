"""Lazy SDK adapter. Construct only after explicit --execute; no dotenv loading."""
import os

class RateLimited(Exception):
    pass


class ProviderClient:
    def __init__(self):
        self.clients = {}

    def complete(self, model, prompt, max_tokens=4096, temperature=None, cache_prefix=None):
        if model == 'gemini-3.8-flash':
            import requests
            body = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
                    'generationConfig': {'maxOutputTokens': max_tokens}}
            if temperature is not None:
                body['generationConfig']['temperature'] = temperature
            response = requests.post(
                'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent',
                headers={'x-goog-api-key': os.environ['GOOGLE_API_KEY']},
                json=body, timeout=120)
            if response.status_code == 429:
                raise RateLimited('gemini 429')
            response.raise_for_status()
            data = response.json()
            candidates = data.get('candidates') or []
            candidate = candidates[0] if candidates else {}
            blocked = bool(data.get('promptFeedback', {}).get('blockReason')) or candidate.get('finishReason') in {
                'SAFETY', 'BLOCKLIST', 'PROHIBITED_CONTENT', 'SPII', 'IMAGE_SAFETY'}
            answer = '' if blocked else ''.join(
                part.get('text', '') for part in candidate.get('content', {}).get('parts', [])
                if not part.get('thought'))
            return {'answer': answer, 'refusal': blocked, 'stop_reason': candidate.get('finishReason'),
                    'model_returned': data.get('modelVersion'), 'usage': data.get('usageMetadata', {})}
        if model.startswith('claude-'):

            if 'anthropic' not in self.clients:
                from anthropic import Anthropic
                self.clients['anthropic'] = Anthropic(max_retries=0)
            content = prompt
            if cache_prefix and prompt.startswith(cache_prefix):
                # Prompt caching: identical text, split into two blocks; the shared prefix (instructions + articles) is billed as a cache read.
                content = [{'type': 'text', 'text': cache_prefix, 'cache_control': {'type': 'ephemeral'}},
                           {'type': 'text', 'text': prompt[len(cache_prefix):]}]
            kwargs = dict(model=model, max_tokens=max_tokens, messages=[{'role': 'user', 'content': content}])
            # Claude Sonnet 5.5 does not accept sampling parameters; PREREG says "temperature 0 where supported".
            r = self.clients['anthropic'].messages.create(**kwargs)
            return {'answer': ''.join(b.text for b in r.content if b.type == 'text'), 'stop_reason': r.stop_reason,
                    'model_returned': r.model, 'usage': r.usage.model_dump()}
        from openai import OpenAI
        groq = model.startswith('qwen/')
        vendor = 'groq' if groq else 'openai'
        if vendor not in self.clients:
            self.clients[vendor] = OpenAI(api_key=os.environ.get('GROQ_API_KEY'), base_url='https://api.groq.com/openai/v1', max_retries=0) if groq else OpenAI(max_retries=0)
        kwargs = dict(model=model, messages=[{'role': 'user', 'content': prompt}])
        kwargs['max_tokens' if groq else 'max_completion_tokens'] = max_tokens
        # GPT-5 fixed-temperature variants do not accept temperature=0.
        if temperature is not None and not model.startswith('gpt-5'):
            kwargs['temperature'] = temperature
        r = self.clients[vendor].chat.completions.create(**kwargs)
        message = r.choices[0].message
        return {'answer': message.content or '', 'refusal': bool(getattr(message, 'refusal', None)), 'stop_reason': r.choices[0].finish_reason,
                'model_returned': r.model, 'usage': r.usage.model_dump() if r.usage else {}}
