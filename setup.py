from distutils.core import setup

setup(
    name='PassiveTLDCheck',
    version='0.03',
    author='ThreatSTOP',
    author_email='ta@threatstop.com',
    packages=['passive_standalone'],
    scripts=['farsight_standalone.py', 'createexcel.py', 'utils.py'],
    url='',
    license='LICENSE.txt',
    description='Check TOP TLDs per IP via Passive DNS.',
    long_description=open('README.txt').read(),
    install_requires=[
        'requests==2.19.1',
        'openpyxl==2.5.9',
        'tldextract==2.2.0']
)
