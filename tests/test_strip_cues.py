import unittest
from pipeline.strip_cues import strip_cues, leak_scan
class StripTests(unittest.TestCase):
    def test_dateline(self):
        text,report=strip_cues('MOSCÚ (Sputnik) – El presidente llegó a Lima. (EFE)')
        self.assertEqual(text,'El presidente llegó a Lima. [medio]')
        self.assertEqual(len(report),2)
    def test_boilerplate(self):
        text,report=strip_cues('Por Ana Pérez\nUna noticia.\nSíguenos en Telegram\n© 2026 RT\nhttps://rt.com/a')
        self.assertEqual(text,'Una noticia.')
        self.assertTrue(report)
    def test_boundaries(self):
        text,_=strip_cues('El arte y el partido continúan. RT pudo saber que llegó.')
        self.assertIn('arte',text); self.assertIn('partido',text); self.assertNotIn('pudo saber',text)
    def test_leaks(self):
        self.assertEqual(len(leak_scan('EFE, France 24 y teleSUR')['remaining_cues']),3)
        self.assertEqual(leak_scan('arte del partido')['remaining_cues'],[])
    def test_references(self):
        text,_=strip_cues('Infobae y El Tiempo: informa esta agencia. DW y AFP. Clarín')
        self.assertEqual(leak_scan(text)['remaining_cues'],[])

class NewOutletCueTests(unittest.TestCase):
    def test_new_outlets_and_canonical_host(self):
        original='El País, La Nación, BioBioChile, Deutsche Welle y actualidad-rt.com. Partido y ARTISTA.'
        clean, report=strip_cues(original)
        self.assertEqual(leak_scan(clean)['remaining_cues'], [])
        self.assertNotIn('actualidad-rt.com',clean)
        self.assertNotIn('Deutsche Welle',clean)
        self.assertIn('ARTISTA',clean)
        self.assertGreaterEqual(len(report),5)

class CaseAndAmbiguityTests(unittest.TestCase):
    def test_lowercase_agency_tags_survive(self):
        clean, _=strip_cues('Texto. afp / efe / dw / rt / sputnik')
        self.assertIn('afp / efe / dw / rt', clean)
        self.assertEqual(leak_scan(clean)['remaining_cues'],[])
    def test_common_country_phrases_survive(self):
        original='En el país, la nación celebró el acuerdo. El País lo publicó.'
        clean, _=strip_cues(original)
        self.assertIn('el país',clean)
        self.assertIn('la nación',clean)
        self.assertNotIn('El País',clean)


class RegressionTests(unittest.TestCase):
    def test_reproductions(self):
        for original, expected in [
            ('todo el tiempo que duró', 'todo el tiempo que duró'),
            ('el comercio con EE.UU.', 'el comercio con EE.UU.'),
            ('"RT miente", dijo el ministro', '"[medio] miente", dijo el ministro'),
            ('RT en Español informó', '[medio]'),
            ('agencia EFE', 'agencia [medio]'),
            ('arte partido rt', 'arte partido rt'),
        ]:
            with self.subTest(original=original):
                self.assertEqual(strip_cues(original)[0], expected)

    def test_all_ambiguous_names_and_acronyms(self):
        names = ['El Tiempo','El Comercio','El Universal','El País','La Nación',
                 'La Tercera','La República','El Deber','Última Hora','El Universo',
                 'La Prensa','Semana','Milenio','Primicias','RT','EFE','AFP','DW']
        for name in names:
            self.assertEqual(strip_cues(name)[0], '[medio]')
            self.assertEqual(strip_cues(name.lower())[0], name.lower())

    def test_scan_and_ledger(self):
        self.assertEqual(leak_scan('rt RT [medio] el tiempo El Tiempo')['medio_tokens'], 1)
        self.assertEqual(len(leak_scan('rt RT [medio] el tiempo El Tiempo')['remaining_cues']), 2)
        clean, ledger = strip_cues('agencia EFE')
        self.assertEqual(ledger[0]['removed'], 'EFE')
        self.assertEqual(ledger[0]['replacement'], '[medio]')

if __name__=='__main__': unittest.main()
