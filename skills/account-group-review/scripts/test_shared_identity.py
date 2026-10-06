import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from shared_identity import resolve


class SharedIdentityTests(unittest.TestCase):
    def test_two_groups_follow_same_identity_and_asset_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.viewprinter/content-memory').mkdir(parents=True)
            art=root/'banner.jpg';art.write_bytes(b'banner1')
            identity=root/'identity.json';d={'revision':2,'identity':{'organizationId':'o','accountId':'a','proposed':{'name':'Shared name'},'application':{'status':'owner-confirmed'}},'assets':[{'id':'banner','src':'banner.jpg','sha256':hashlib.sha256(art.read_bytes()).hexdigest()}]};identity.write_text(json.dumps(d))
            source={'accounts':[{'ref':'local','organizationId':'o','accountId':'a','role':'group-specific','identityRef':'../identity.json','assetBindings':{'cover':'banner'}}],'assets':[{'id':'cover','src':'old.jpg'}]}
            output=[]
            for name in ('one','two'):
                folder=root/name;folder.mkdir();result=resolve(source,folder);output.append(result)
                self.assertEqual(result['accounts'][0]['proposed']['name'],'Shared name')
                self.assertEqual(result['accounts'][0]['role'],'group-specific')
                self.assertEqual(result['accounts'][0]['application']['status'],'owner-confirmed')
                self.assertEqual((folder/result['assets'][0]['src']).read_bytes(),b'banner1')
            self.assertEqual(output[0]['assets'][0]['sha256'],output[1]['assets'][0]['sha256'])
            self.assertNotIn('proposed',source['accounts'][0])
            d['identity']['accountId']='wrong';identity.write_text(json.dumps(d))
            with self.assertRaises(ValueError):resolve(source,root/'one')

if __name__=='__main__':unittest.main()
