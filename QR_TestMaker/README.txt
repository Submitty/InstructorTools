To use...

0. First time... just run
   python3 make_all.py

   to see an example of what is produced.  Then you can replace the
   samples with your own data/test.

---------------------------------

1. prepare the test_seating.txt file
   (can use the seating file produced by Rainbow Grades)

   the columns are:  lastname, firstname, username, section, building, room, zone, row, seat, all_other_information (grabs the rest of the line, final field can have spaces)

   N/A = not applicable is available for many fields

2. if the students have uploaded crib sheets, name them 
   students_notes/username.pdf and they will be attached to each test

3. prepare your test template as a pdf.  Leave some space in the upper
   half of the page for the preprinted zone/name/qr code.  (may need
   adjustment... )

4. run:
   python3 make_all.py

5. files will be produced in to_print folder organized into subdirectories by zone

6. tweak overlay.tex if desired and re-run
