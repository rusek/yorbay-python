from __future__ import unicode_literals

def osa_distance(s1, s2):
    """
    Compute optimal string alignment distance between two strings.

    See:
        http://en.wikipedia.org/wiki/Damerau%E2%80%93Levenshtein_distance
    """

    if len(s1) < len(s2):
        s2, s1 = s1, s2

    l1, l2 = len(s1), len(s2)

    da = [0] * (l2 + 1)
    db = range(l2 + 1)
    dc = [0] * (l2 + 1)

    for i1 in xrange(l1):
        da[0] = i1 + 1
        for i2 in xrange(l2):
            cost = int(s1[i1] != s2[i2])
            t = min(db[i2 + 1] + 1, da[i2] + 1, db[i2] + cost)
            if i1 > 0 and i2 > 0 and s1[i1] == s2[i2 - 1] and s1[i1 - 1] == s2[i2]:
                t = min(t, dc[i2 - 1] + cost)
            da[i2 + 1] = t
        da, db, dc = dc, da, db

    return db[l2]


def get_distance_threshold(s):
    return (len(s) + 2) // 4 + 1


def get_similar(s, candidates):
    best, best_dist = None, get_distance_threshold(s)

    for cand in candidates:
        dist = osa_distance(s, cand)
        if dist < best_dist:
            best, best_dist = cand, dist

    return best
