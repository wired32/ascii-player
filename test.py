cor1 = (255, 0, 0)
cor2 = (255, 20, 15)

print(sum(abs(c1 - c2) for c1, c2 in zip(cor1, cor2)))