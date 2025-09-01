WOS_FIELDS = {
    'PT': 'Document Type',
    'AU': 'Authors',
    'TI': 'Title',
    'SO': 'Source',
    'LA': 'Language',
    'DE': 'Keywords',
    'AB': 'Abstract',
    'C1': 'Author Address',
    'RP': 'Repring Adress',
    'CR': 'Cited References',
    'TC': 'Times Cited',
    'PY': 'Publication Year',
    'DI': 'DOI',
}

CROSSREF_AVAILABLE_FIELDS = {
    'author': 'author',
    'Title': 'title',
    'Abstract': 'abstract',
    'Language': 'language',
    'Article References': 'reference',
    'Author References': 'reference',
    'Times Cited': 'is-referenced-by-count',
    'Publication Year': 'created',
    'DOI': 'DOI'
}

REFERENCE_FIELDS = ["DOI", "article-title", "author"]