import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pipeline'))
from source_client import Robots
from config import REFERENCE_DOMAINS, COMPARISON_DOMAINS
class SourcePolicyTests(unittest.TestCase):
    def test_google_rss_disallowed(self):
        robots=Robots('User-agent: *\nDisallow: /\nAllow: /home$\nAllow: /topics/')
        self.assertFalse(robots.can_fetch('ResearchClient','https://news.google.com/rss/search?q=Mexico'))
        self.assertTrue(robots.can_fetch('ResearchClient','https://news.google.com/home'))
        self.assertFalse(robots.can_fetch('ResearchClient','https://news.google.com/home/secret'))
    def test_wildcard_specific_allow_and_multiple_groups(self):
        robots=Robots('User-agent: *\nDisallow: /private*\nAllow: /private/public/\nUser-agent: *\nDisallow: /*?preview=true$')
        self.assertFalse(robots.can_fetch('ResearchClient','https://example.org/private-data'))
        self.assertTrue(robots.can_fetch('ResearchClient','https://example.org/private/public/story'))
        self.assertFalse(robots.can_fetch('ResearchClient','https://example.org/story?preview=true'))
    def test_specific_agent(self):
        robots=Robots('User-agent: *\nDisallow: /\nUser-agent: ResearchClient\nAllow: /')
        self.assertTrue(robots.can_fetch('ResearchClient/1.0','https://example.org/article'))
        self.assertFalse(robots.can_fetch('AnotherClient','https://example.org/article'))
    def test_source_roles(self):
        for domain in ['telesurtv.net','actualidad-rt.com','noticiaslatam.lat','hispantv.com','prensa-latina.cu']:
            self.assertNotIn(domain,REFERENCE_DOMAINS)
        self.assertIn('telesurtv.net',COMPARISON_DOMAINS)

class RedirectPolicyTests(unittest.TestCase):
    def test_redirect_destination_is_checked_before_fetch(self):
        from unittest.mock import Mock
        from source_client import Client
        client=Client()
        client.allowed=Mock(side_effect=[True,False])
        client.raw=Mock(return_value=({'status':302,'location':'https://blocked.example/private'},''))
        with self.assertRaisesRegex(ValueError,'robots disallow'):
            client.get('https://allowed.example/story')
        self.assertEqual(client.raw.call_count,1)
        self.assertEqual(client.allowed.call_args.args[0],'https://blocked.example/private')
    def test_forbidden_opens_domain_circuit(self):
        from unittest.mock import Mock
        from source_client import Client
        client=Client();client.allowed=Mock(return_value=True)
        client.raw=Mock(return_value=({'status':403},'denied'))
        with self.assertRaisesRegex(ValueError,'HTTP 403'): client.get('https://example.org/a')
        with self.assertRaisesRegex(ValueError,'circuit breaker'): client.get('https://example.org/b')
        self.assertEqual(client.raw.call_count,1)

if __name__=='__main__': unittest.main()
