"""冻结的 I07 tri 臂登记（i07-ps3-20261011，25 个 = 5 癌 × 5 折）：best.pt 与 run.json 的 sha256。

这是 cache.py 加载 ckpt 时的信任锚：本文件是 .py，受源码身份门（git HEAD / GIT_STAMP）逐文件指纹保护，
改动它会让身份门判 dirty 或 commit 不符（Codex 首审 finding 2，2026-11-08）。
生成自仓库内 checkpoint-sha256.txt 与 results/i07-ps3-20261011/runs/<癌>/fold<k>/tri/run.json；
tests/test_cache.py 核对两者一致。
"""
BACKBONE_RUN = 'i07-ps3-20261011'
# 25 个 tri run.json 共同记录的训练资产指纹（五份 manifest 的 sha256）；缓存导出与使用都必须等于它（复审 R2-2）
ASSETS_FP = {
    'cohort': '289f374698c1a850488414e9e5449870595ab8894065ef99c5b308b082d613d6',
    'rna': 'aa233e63dbceaab56032d8810d8b1418463e6fefcfdf54793dc5259269b08ab4',
    'splits': 'f6e3e4b0747e49dd0ff4fc95e903fcff03e4b5c84a2d33ac251a6be7f58a960f',
    'text': 'de8ef94c2a1c160a786db4be6f6ae97775c4fa88a4b2e712cc053551e8799259',
    'wsi_tokens': '7b19edc44b621d4624173bc9d9d86d56dbc7ca3f1c6d515fae22b8bab5b3e59c',
}
TRI = {
    'BLCA/fold0/tri/best.pt': ('ab980963f291ebe3f85896c96f94b0e66c2c601065526a4dff51d713bad5bb2a',
        '4c1439e17f34a307ab640dcf51524503b1cbb4b06caaa38f78e256bb402cd4b2'),
    'BLCA/fold1/tri/best.pt': ('bd080e72025ddf2306029763602ba0ba2bce8a67c7a91cfe86ac2de49bb1687b',
        '6d2acb50c62e2c212c569800e9920847c8f1297af46b5929527f962c03793014'),
    'BLCA/fold2/tri/best.pt': ('a8828e9ca77e532e8ba1322689a7572cb8efa5b769feefb1ebb0b7a7fcca1430',
        '33dd8f0cfc9f2b1a559123d515f96db5eba91742887e3d30b2e2a8c78632933a'),
    'BLCA/fold3/tri/best.pt': ('5e6f86ec46d5d58087cf7941e0f47652f00716101106ebf6a27311e62da3c099',
        '5d9deae8358af87859891bbf036fdcfd24510fe8fa67deaff65199962e4572b8'),
    'BLCA/fold4/tri/best.pt': ('13703e2e7eed9687a46f829a1531cae5ffd634e6e335331c04937d17a9f91c8c',
        'ec8d0afb0e3de90bd0c850fe259e67995ea922e03a616814081f02ea19e10475'),
    'BRCA/fold0/tri/best.pt': ('2201c88c2964704687a5068ea1e36e7a26fd7d39fc9371395e48c30855fa889f',
        '7a6a8d7b0b3cca679313387218d975d64b9e3f4900491539248ab91dc5658a91'),
    'BRCA/fold1/tri/best.pt': ('d1e813fc7b91b65a43bb0971f436499e23f1d74ed283aaf3a2c05334609ece92',
        'c4da442adc473bbe6d28f06cdc3bd379dd029e086f27560a0d3288be3715cdd1'),
    'BRCA/fold2/tri/best.pt': ('cec28281de8b633bb315bf611db076ef95f667d1cba482416143495c6b8c9530',
        '1fdd1e6a624f674c23e6e437dcd1bff19ac3ebcd6813a2ce0f9ad2f2f5eb29de'),
    'BRCA/fold3/tri/best.pt': ('4e08bb71b85d781a2d02a8893a47f034213f15fc9cf7afbcef3914cff711a8c0',
        'b5f56e1002c47fef88c51a06593b6c41c7b1f5b88632e428ab1693728ace2f9d'),
    'BRCA/fold4/tri/best.pt': ('9a8e012a8f1d48e5b5851edda041a07169b560cf4d6fcb5985daf4c79447d117',
        'e0997184eac1f6d6c2fed4d4bb8f1664760bf7c158890be9c8c13c46c6fbc606'),
    'LGG/fold0/tri/best.pt': ('5716e3ada4e762989e18a7727d9d3aa7fc569c4618ea5ca7a59ac1beebe1fee3',
        'dbe8f63a55ac1e5cdf76f1e37dd2c635853969ed98ff06f0f8a270cfaeb21cd3'),
    'LGG/fold1/tri/best.pt': ('abd07e13e4db372963a162a4d13ac5252298bd8f55ecd8c97dea6533d8fe3e29',
        '366a0d3a8a27870c8aa0bd61cd5f23ae23f0bab7a99dd805d0f6e29f0e6faa4f'),
    'LGG/fold2/tri/best.pt': ('b6d7581544f25bc9d65282dd8a03bcc6514f0ad8475b1cc18c32c671312b94f5',
        'f75a556f9bda8c98c4c02f788e32b351dff4afdc52870ebbe2db2cc7f6075074'),
    'LGG/fold3/tri/best.pt': ('65a8fa54326ae3c70c53d485e7ccba2daa1ad3776cfcecd9618021a21cfa98aa',
        'd22628840bc90453637daac413b90a6a154f7562371bc9496cb3b8b6e89d8e1f'),
    'LGG/fold4/tri/best.pt': ('6bbf35017fcadd7034097e876fdfe31ba8e9a0cec48c61ff202e4c5f77c62f39',
        '89f25fb716c00437f32728802b86a36cd9de2cfec8fcf66bd2248ef3c198f72c'),
    'LUAD/fold0/tri/best.pt': ('a040e8e44e1293b6f64af4c1ddff2fc719e2f109c0c53704db36d08d5972c1bb',
        '9105f08f44c323dc70657fbfe2ea9346dac86ab372cad9cd38e88e3a4e7fb046'),
    'LUAD/fold1/tri/best.pt': ('05991b3c58f42e9fcc8320c2688803286d8986ab924430330dc99dd36539713e',
        '5e98a4e00cb0c51defbedd5b4f307177b96fbd6a5010dc4f031bd53cd71d5555'),
    'LUAD/fold2/tri/best.pt': ('405b8041ad2d2d2c5244233989f25caaf4f94bb816c62cbad369a798f1ca0f77',
        'dced1e6591e49f202c8b9e802546eeab023e5deb9040224569a35ba7a3e14b52'),
    'LUAD/fold3/tri/best.pt': ('3fb0089562f685a0060ca936cbf4d02b7104a16ce9bbc7ea385730c742e62740',
        '332e09fe94830811b7fbb96756c14a265ad2e4c25ab029011c9675e91b72cfb4'),
    'LUAD/fold4/tri/best.pt': ('4cb24eccd44bd97ee27c85927a50a21264968256595b2b378d5dbc7eb94b0217',
        '83dcdc439a810ac033b8666d460e760e2dd163e63c4f0605368928059f9bcd02'),
    'UCEC/fold0/tri/best.pt': ('51d334d63fb824a067b51cc649f0404b40c35ebefced31673735c8afcfa14b30',
        '7e9af392e12f19916c6adf9bfe50490246cba9eb7f1a2bddbd7ac76a5880e96b'),
    'UCEC/fold1/tri/best.pt': ('568a9845dc1a9a1e5bdfa26233469ee8766879f47b3d8aa9c6e7d1bcdca3fd0e',
        '66b595ddc17f08b6adc2472515cf70809fc33b9447789c2d1f99b5314d172854'),
    'UCEC/fold2/tri/best.pt': ('5e2bce28ef944c308fb4cfdf21b16997eb811b39b913fdeff219ef80ffd32833',
        '96a177843a1fb81e1bf680cfd74d7a022d7a4973700bc3250ac74c094b235db1'),
    'UCEC/fold3/tri/best.pt': ('3cf1463a6d706983fe4d828355a6c860b669572e4d6419e983a5b97132c5aee8',
        'dc1b29b6a201739044e26aa15c5962e2d6a7c8e27821ef181a6fd3416e8e5a93'),
    'UCEC/fold4/tri/best.pt': ('bfdcb1ab8c7c4ce0aadd7234faf9e7a3c5b7f53f5454ca4087601db6abf16206',
        '880606453e0f42bdedbe8a9079879c88c439f8f1bb85bf6167479081593d15fa'),
}
