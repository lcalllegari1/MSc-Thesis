// Tiny inner circuit: proves knowledge of x such that x^2 == y (y is public).
fn main(x: Field, y: pub Field) {
    assert(x * x == y);
}
