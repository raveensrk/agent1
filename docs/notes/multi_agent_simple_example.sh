character=("X")
character+=("Y")
character+=("Z")
preference=("Beach")
preference+=("Mountain")
preference+=("Forest")
prompts=("Talk like ${character[0]}.")
prompts+=("Talk like ${character[1]}.")
prompts+=("Talk like ${character[2]}.")

echo "==========================================" >> "debate.txt"
echo "We are a group fo 3 friends- ${character[@]} who is planning for a trip. Find out the best place. We each have preference ${preference[@]} respectively." > "debate.txt"
echo "==========================================" >> "debate.txt"

for i in {0..10}; do
	y=$((i%3))
	echo "==========================================" >> "debate.txt"
	echo "Character: ${character[$y]}" >> "debate.txt"
	echo "==========================================" >> "debate.txt"
	claude -p "${prompts[$y]} $(cat debate.txt)" >> "debate.txt"
	echo "==========================================" >> "debate.txt"
done
