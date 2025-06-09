from sklearn.feature_extraction.text import TfidfVectorizer
import sys

def handle(req):
    corpus = [req]
    vectorizer = TfidfVectorizer(stop_words='english')
    X = vectorizer.fit_transform(corpus)
    feature_names = vectorizer.get_feature_names_out()
    scores = X.toarray()[0]

    top_keywords = sorted(zip(feature_names, scores), key=lambda x: x[1], reverse=True)[:5]
    keywords = [kw for kw, _ in top_keywords]
    return ','.join(keywords)


if __name__ == "__main__":
    req = sys.stdin.read()
    res = handle(req)
    print(res)