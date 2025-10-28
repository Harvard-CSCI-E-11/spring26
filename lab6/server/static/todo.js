def celebrities_to_html(celebs):
    html = ''
    for celeb in celebs:
        html += f"Name: {celeb.get('Name')} Confidence: {celeb.get('MatchConfidence'):2.4}% "
        for url in celeb.get('Urls', []):
            html += f"<a target='_' href='https://{url}'>[link]</a>"
        html += "<br/>\n"
    return html
